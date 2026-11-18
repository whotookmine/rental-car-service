"""Bookings. Creation is nested under the provider a booking is made with."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from sqlalchemy import select

from app.auth.dependencies import get_current_user, require_registered_user
from app.auth.models import User, UserRole
from app.bookings.dependencies import get_visible_booking_or_404
from app.bookings.models import Booking
from app.bookings.rules import (
    ensure_class_has_room,
    ensure_delivery_within_radius,
    ensure_one_way_route_enabled,
    ensure_provider_is_active,
    ensure_reviewed_booking_stays_ended,
    ensure_room_for_another_booking,
    resolve_branch_for_provider,
    resolve_vehicle_class_for_provider,
)
from app.bookings.schemas import BookingCreate, BookingRead, BookingUpdate
from app.core.clock import today
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider
from app.vehicle_classes.models import VehicleClass
from app.waitlist.rules import settle_queue

router = APIRouter(tags=["bookings"])


@router.post(
    "/providers/{provider_id}/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Book a provider for a rental period",
    description=(
        "Creates a booking for the calling registered user. The provider is part "
        "of the path because a booking cannot exist without one, and it is fixed "
        "for the life of the booking. The body names which of that provider's "
        "vehicle classes is being rented, which is fixed for the same reason."
    ),
    responses={
        403: {"description": "Admins manage rentals rather than holding them."},
        404: {"description": "Provider not found."},
        409: {
            "description": (
                "The provider has retired and is no longer accepting bookings, "
                "the user already holds the maximum active bookings, the vehicle "
                "class or pickup branch belongs to a different provider, or the "
                "class has no vehicle both free and on the road for the whole "
                "requested period. That last refusal says which it is: taken by "
                "other bookings, off the road for maintenance, or both, so the "
                "caller knows whether waiting could help."
            )
        },
        422: {"description": "The vehicle class or pickup branch does not exist."},
    },
)
def create_booking(
    payload: BookingCreate,
    current_user: User = Depends(require_registered_user),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> BookingRead:
    ensure_provider_is_active(provider)
    # All branches and the vehicle class are resolved before the cap is taken,
    # so that a request naming the wrong class or branch is told what is actually
    # wrong rather than being turned away for a limit it would still hit after
    # fixing the bad value.
    vehicle_class = resolve_vehicle_class_for_provider(
        db, provider, payload.vehicle_class_id
    )
    pickup_branch = resolve_branch_for_provider(db, provider, payload.pickup_branch_id)

    # Resolve the drop-off branch when one is named. Null means round-trip.
    dropoff_branch = None
    if payload.dropoff_branch_id is not None:
        dropoff_branch = resolve_branch_for_provider(
            db, provider, payload.dropoff_branch_id
        )
        # Only enforce the one-way check when the two branches differ. A caller
        # who sends the same id for both is booking a round-trip and need not
        # have enabled anything; treat it as omitted.
        if dropoff_branch.id != pickup_branch.id:
            ensure_one_way_route_enabled(db, pickup_branch, dropoff_branch)
        else:
            dropoff_branch = None  # same branch = round-trip; store null

    # Delivery validation. Both fields arrive together (schema enforces the pair).
    # The branch radius check is state, not shape, so it is a 409 here.
    if payload.delivery_address is not None:
        ensure_delivery_within_radius(pickup_branch, payload.delivery_distance_km)

    # The caller's own limit first, then the world's. It is the one they control
    # entirely -- they can free a slot by deleting a booking of their own -- and
    # checking it first skips the per-day capacity query for a request that was
    # going to fail regardless.
    #
    # The order is also the lock order: owner row, then vehicle class row. Every
    # path that takes both takes them this way round; two routes taking them in
    # opposite orders is how a deadlock is built.
    ensure_room_for_another_booking(db, current_user.id)
    ensure_class_has_room(db, vehicle_class, payload.start_date, payload.end_date)

    booking = Booking(
        # From the token. A caller cannot book on someone else's behalf by
        # naming them, because the request has no say in who owns this.
        user_id=current_user.id,
        provider_id=provider.id,
        vehicle_class_id=vehicle_class.id,
        pickup_branch_id=pickup_branch.id,
        dropoff_branch_id=dropoff_branch.id if dropoff_branch else None,
        start_date=payload.start_date,
        end_date=payload.end_date,
        delivery_address=payload.delivery_address,
        delivery_distance_km=payload.delivery_distance_km,
        collection_address=payload.collection_address,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return BookingRead.model_validate(booking)


@router.get(
    "/bookings",
    response_model=list[BookingRead],
    summary="List bookings visible to you",
    description=(
        "A registered user receives their own bookings; an admin receives every "
        "booking in the system. Oldest rental period first. A user with no "
        "bookings receives an empty list."
    ),
)
def list_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BookingRead]:
    # Scope is decided here from the caller's role and applied in the query, so
    # there is no parameter a caller could pass to widen it. Ordered explicitly:
    # without it PostgreSQL returns rows in whatever order it likes, and that
    # order changes between runs.
    stmt = select(Booking).order_by(Booking.start_date, Booking.id)
    if current_user.role != UserRole.admin:
        stmt = stmt.where(Booking.user_id == current_user.id)

    return [BookingRead.model_validate(b) for b in db.scalars(stmt).unique()]


@router.get(
    "/bookings/{booking_id}",
    response_model=BookingRead,
    summary="Fetch a booking",
    description=(
        "A registered user may fetch their own bookings; an admin may fetch any. "
        "Answers 404 both for a booking that does not exist and for one belonging "
        "to another user, so that booking identifiers cannot be walked to measure "
        "how much other people are renting."
    ),
    responses={404: {"description": "Booking not found."}},
)
def get_booking(
    booking: Booking = Depends(get_visible_booking_or_404),
) -> BookingRead:
    return BookingRead.model_validate(booking)


@router.put(
    "/bookings/{booking_id}",
    response_model=BookingRead,
    summary="Change the dates of a booking",
    description=(
        "Replaces the rental period. The same shape rules as creation apply — end "
        "on or after start, at most thirty days — but a start date in the past is "
        "allowed here, so a rental already underway can be extended. Neither the "
        "provider nor the vehicle class can be changed: sending either is "
        "refused, not ignored."
    ),
    responses={
        404: {"description": "Booking not found."},
        409: {
            "description": (
                "The booking has been reviewed and the new dates would leave it "
                "not yet ended, the owner already holds the maximum active "
                "bookings, or the vehicle class has no vehicle both free and on "
                "the road for the new rental period — including when a "
                "maintenance window covers part of it."
            )
        },
    },
)
def update_booking(
    payload: BookingUpdate,
    booking: Booking = Depends(get_visible_booking_or_404),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BookingRead:
    # Checked before the cap because this refusal is absolute: no amount of
    # freeing slots will make a reviewed booking movable into the future, whereas
    # the cap clears on its own as rental periods end. Telling the caller the
    # permanent blocker first is more use than telling them the transient one.
    ensure_reviewed_booking_stays_ended(db, booking.id, payload.end_date)

    # Only re-check the cap when the edit would leave the booking active. A
    # booking that has ended and stays ended occupies no slot, so an owner at the
    # limit must still be able to correct its dates. The booking is excluded from
    # its own count, or an owner holding the maximum could never edit any of them.
    if payload.end_date >= today():
        ensure_room_for_another_booking(
            db,
            booking.user_id,
            excluding_booking_id=booking.id,
            # An admin may be editing someone else's booking; the refusal should
            # say whose limit was reached rather than address them as the owner.
            owner_is_caller=booking.user_id == current_user.id,
        )

    # Capacity for the new dates, measured against the booking's own class and
    # excluding the booking itself -- it is moving, not being added. Taken after
    # the owner cap so that the lock order matches creation's. Since ticket 41
    # this also refuses dates where the class's cars are off the road for
    # maintenance, and it applies to an admin exactly as to the owner: both reach
    # this line through the same route.
    #
    # Unlike the owner cap this is checked whatever the new dates are, including
    # ones wholly in the past: a past-dated booking still occupied a car on those
    # days, and an admin correcting history must not be able to record four
    # rentals of a class that only ever had three cars.
    ensure_class_has_room(
        db,
        booking.vehicle_class,
        payload.start_date,
        payload.end_date,
        excluding_booking_id=booking.id,
    )

    booking.start_date = payload.start_date
    booking.end_date = payload.end_date
    db.commit()
    db.refresh(booking)

    return BookingRead.model_validate(booking)


@router.delete(
    "/bookings/{booking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a booking",
    description=(
        "Removes the booking outright. There is no cancelled state and no soft "
        "delete: the row is gone, and the slot it occupied is free immediately. "
        "If anyone is waiting for that vehicle class, the capacity this releases is "
        "offered to whoever has waited longest and can use it. Answers 404 for a "
        "booking belonging to another user, exactly as for one that does not exist."
    ),
    responses={404: {"description": "Booking not found."}},
)
def delete_booking(
    booking: Booking = Depends(get_visible_booking_or_404),
    db: Session = Depends(get_db),
) -> Response:
    # The class row is locked before the delete, not after, and for the whole of
    # what follows. Deleting and then offering is two steps over one piece of
    # state: without the lock, two simultaneous cancellations would both read the
    # same queue, both find the same person at the front, and both offer them the
    # capacity -- one car promised twice, and the second person in the queue never
    # hearing anything.
    #
    # Lock order is owner, then vehicle class, then vehicle. No owner lock is taken
    # here: deleting only ever lowers the owner's active count, so there is no
    # count-then-write race to protect.
    vehicle_class_id = booking.vehicle_class_id
    db.execute(
        select(VehicleClass.id)
        .where(VehicleClass.id == vehicle_class_id)
        .with_for_update()
    )

    db.delete(booking)
    # Flushed, not committed: the offer below has to see the booking gone when it
    # measures what is free, and both have to land together or not at all. A commit
    # here would leave a window where the car is free and nobody has been told.
    db.flush()

    # Settles rather than offering once: a cancellation is also a fine moment to
    # notice that an earlier claim lapsed, and freeing one car may let two offers be
    # made if another claim expired meanwhile. `settle_queue` offers exactly as many
    # times as there is room for and then stops.
    settle_queue(db, vehicle_class_id)

    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
