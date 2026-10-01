"""The waitlist: queueing for a vehicle class that is full for the dates you want.

Joining is nested under the provider, as booking is, because a queue cannot exist
without one. Reading and leaving address the entry directly.

Admins do not queue, for the same reason they do not hold bookings: they manage
rather than rent, and a waitlist place is a claim on inventory.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_registered_user
from app.auth.models import User
from app.bookings.models import Booking
from app.bookings.rules import (
    ensure_class_has_room,
    ensure_one_way_route_enabled,
    ensure_provider_is_active,
    ensure_room_for_another_booking,
    resolve_branch_for_provider,
)
from app.bookings.schemas import BookingRead
from app.core.clock import now
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider
from app.vehicle_classes.models import VehicleClass
from app.waitlist.dependencies import get_own_waitlist_entry_or_404
from app.waitlist.models import WaitlistEntry
from app.waitlist.rules import (
    claim_is_live,
    claim_state,
    ensure_class_is_full,
    is_active,
    offer_released_capacity,
    position_of,
    refuse_duplicate_place,
    resolve_class_for_provider,
)
from app.waitlist.schemas import (
    ClaimConvert,
    WaitlistEntryCreate,
    WaitlistEntryRead,
)

router = APIRouter(tags=["waitlist"])


def _read(db: Session, entry: WaitlistEntry) -> WaitlistEntryRead:
    """Build the response, computing position and activity at read time.

    Every mapped column is copied across **by reflection** rather than named one by
    one, and that is deliberate. Ticket 44 added `offered_at` to the model and to
    the schema and this function still listed the fields by hand, so the new field
    silently took its default and every response reported `offered_at: null` while
    the database held a timestamp. A field that is sometimes a lie is worse than an
    absent one -- the same defect as the nested provider ratings in ticket 50, found
    the same way: by a test that knew what the answer should be.

    Reflection means adding a column cannot quietly fail to appear. The computed
    fields are then layered on top, and they are the only ones a reader has to think
    about.
    """
    data = {
        attr.key: getattr(entry, attr.key)
        for attr in inspect(entry).mapper.column_attrs
    }
    data["vehicle_class"] = entry.vehicle_class
    data["position"] = position_of(db, entry)
    data["is_active"] = is_active(entry)
    data["state"] = claim_state(entry, now())
    return WaitlistEntryRead.model_validate(data)


@router.post(
    "/providers/{provider_id}/waitlist_entries",
    response_model=WaitlistEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Join the waitlist for a full vehicle class",
    description=(
        "Queues the calling user for one of this provider's vehicle classes over an "
        "exact date range. The queue is identified by provider, class and that "
        "range: capacity released for the 10th to the 12th is not capacity for the "
        "9th to the 15th, so those are different queues. Refused if the class is "
        "**not** full for those dates — the answer then is to book it. Your place "
        "is the order you joined, and nothing else moves it."
    ),
    responses={
        403: {"description": "Admins do not join waitlists."},
        404: {"description": "Provider not found."},
        409: {
            "description": (
                "The provider has retired, the class belongs to a different "
                "provider, the class is not full for those dates, or you are "
                "already in that queue."
            )
        },
        422: {
            "description": (
                "The vehicle class does not exist, or the date range is malformed, "
                "longer than thirty days, or in the past."
            )
        },
    },
)
def join_waitlist(
    payload: WaitlistEntryCreate,
    current_user: User = Depends(require_registered_user),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> WaitlistEntryRead:
    ensure_provider_is_active(provider)
    vehicle_class = resolve_class_for_provider(
        db, provider, payload.vehicle_class_id
    )

    # The lock before the fullness check, for the reason every capacity check here
    # locks: measuring and then writing is a race. Here the race is mild -- joining
    # a queue that stopped being full a moment ago costs nothing but a pointless
    # entry -- but tickets 44 to 46 offer released capacity under this same lock,
    # and a queue that can be joined outside it could gain an entry mid-offer.
    #
    # Lock order is owner, then vehicle class, then vehicle. No owner lock is taken
    # here: there is no per-user limit on waitlist places to protect.
    db.execute(
        select(VehicleClass.id)
        .where(VehicleClass.id == vehicle_class.id)
        .with_for_update()
    )

    refuse_duplicate_place(
        db,
        user_id=current_user.id,
        vehicle_class=vehicle_class,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    ensure_class_is_full(db, vehicle_class, payload.start_date, payload.end_date)

    entry = WaitlistEntry(
        # From the token. Nobody queues on anyone else's behalf.
        user_id=current_user.id,
        provider_id=provider.id,
        vehicle_class_id=vehicle_class.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        # The instant that *is* the queue order. From the one clock helper.
        created_at=now(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _read(db, entry)


@router.get(
    "/waitlist_entries",
    response_model=list[WaitlistEntryRead],
    summary="List your waitlist entries and where you stand",
    description=(
        "The calling user's own places in queues, each with its `position` — 1 is "
        "the front — and whether it is still `is_active`. An entry whose date range "
        "has passed stays visible as your own record but is inert: no release will "
        "be offered to it. Ordered by the range wanted, then by when you joined. A "
        "user in no queues receives an empty list."
    ),
)
def list_my_waitlist_entries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WaitlistEntryRead]:
    # Scoped from the token, with no parameter that could widen it.
    entries = db.scalars(
        select(WaitlistEntry)
        .where(WaitlistEntry.user_id == current_user.id)
        .order_by(
            WaitlistEntry.start_date,
            WaitlistEntry.end_date,
            WaitlistEntry.created_at,
            WaitlistEntry.id,
        )
    ).unique().all()
    return [_read(db, entry) for entry in entries]


@router.delete(
    "/waitlist_entries/{waitlist_entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave a waitlist",
    description=(
        "Removes your place outright. Everyone behind you moves up by one "
        "immediately, because positions are counted from join order rather than "
        "stored — there is no renumbering to go wrong. Another user's entry answers "
        "404, exactly as one that does not exist."
    ),
    responses={404: {"description": "Waitlist entry not found."}},
)
def leave_waitlist(
    entry: WaitlistEntry = Depends(get_own_waitlist_entry_or_404),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(entry)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _require_live_claim(db: Session, entry: WaitlistEntry) -> None:
    """Refuse unless this entry is holding a live claim right now.

    Each refusal names the actual state, because four quite different things bring
    someone here and only one of them is worth retrying. Expiry in particular is
    judged at this moment rather than by anything having marked the row, so a claim
    that lapsed overnight is refused the first time it is reached.
    """
    state = claim_state(entry, now())
    if state == "claimed":
        return

    reasons = {
        "waiting": (
            "Nothing has been offered to you for this waitlist entry yet. You are "
            "still in the queue."
        ),
        "expired": (
            "The claim on this waitlist entry has expired and the capacity has "
            "passed on. Your place in the queue is gone; join again if you still "
            "want these dates."
        ),
        "converted": (
            "This claim has already been turned into a booking. A claim can only "
            "be taken once."
        ),
        "declined": (
            "You declined this claim, which released the capacity immediately. "
            "Join the queue again if you have changed your mind."
        ),
    }
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail=reasons[state]
    )


@router.post(
    "/waitlist_entries/{waitlist_entry_id}/claim",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Take the claim offered to you, as a booking",
    description=(
        "Turns a live claim into a booking for the class and dates you queued for. "
        "Those are **not** in the body: the car is being held for those days, and "
        "claiming it for different ones would be a new request rather than taking "
        "the offer. Only the pickup branch, and optionally a drop-off, are yours to "
        "choose here.\n\n"
        "This succeeds even though the class reads as full to everyone else — that "
        "is what the claim is for. It is refused if the claim has expired, has "
        "already been taken, was declined, or was never offered, and the message "
        "says which. Taking the claim consumes it."
    ),
    responses={
        404: {"description": "Waitlist entry not found."},
        409: {
            "description": (
                "There is no live claim on this entry, the provider has retired, "
                "the pickup or drop-off branch belongs to another provider, the "
                "one-way direction is not enabled, or you already hold the maximum "
                "active bookings."
            )
        },
        422: {"description": "A branch named in the body does not exist."},
    },
)
def convert_claim(
    payload: ClaimConvert,
    entry: WaitlistEntry = Depends(get_own_waitlist_entry_or_404),
    db: Session = Depends(get_db),
) -> BookingRead:
    # The class row first, for the whole of what follows: this reads occupancy and
    # then writes a booking, which is the same count-then-insert race every capacity
    # check here guards against.
    db.execute(
        select(VehicleClass.id)
        .where(VehicleClass.id == entry.vehicle_class_id)
        .with_for_update()
    )
    _require_live_claim(db, entry)

    provider = db.get(Provider, entry.provider_id)
    # A provider can retire while someone is in its queue. Refusing here rather than
    # letting the booking through keeps one rule in one place: a retired provider
    # takes no new bookings, however the booking arrives.
    ensure_provider_is_active(provider)

    pickup_branch = resolve_branch_for_provider(
        db, provider, payload.pickup_branch_id
    )
    dropoff_branch = None
    if payload.dropoff_branch_id is not None:
        dropoff_branch = resolve_branch_for_provider(
            db, provider, payload.dropoff_branch_id
        )
        if dropoff_branch.id != pickup_branch.id:
            ensure_one_way_route_enabled(db, pickup_branch, dropoff_branch)
        else:
            dropoff_branch = None  # same branch at both ends is a round trip

    # The owner's own cap still applies. A claim is an offer of a car, not an
    # exemption from the rule about how many a person may hold -- and someone at the
    # cap who is handed a fourth would otherwise end up holding four.
    #
    # Lock order: the class row is already held above, and the owner row is taken
    # inside here. That is the one place in the service where the class is locked
    # before the owner, and it is safe only because this route takes no further
    # locks afterwards; see docs/SPEC.md.
    ensure_room_for_another_booking(db, entry.user_id)

    # Their own claim is excluded from the count. Without this the holder would be
    # refused by the very reservation that was made for them, which is the one thing
    # an exclusive claim must never do.
    ensure_class_has_room(
        db,
        entry.vehicle_class,
        entry.start_date,
        entry.end_date,
        excluding_claim_entry_id=entry.id,
    )

    booking = Booking(
        user_id=entry.user_id,
        provider_id=entry.provider_id,
        vehicle_class_id=entry.vehicle_class_id,
        pickup_branch_id=pickup_branch.id,
        dropoff_branch_id=dropoff_branch.id if dropoff_branch else None,
        start_date=entry.start_date,
        end_date=entry.end_date,
    )
    db.add(booking)
    db.flush()

    # The claim is spent. `converted_at` is what every rule reads; the booking id is
    # for anyone tracing where a booking came from.
    entry.converted_at = now()
    entry.converted_booking_id = booking.id

    db.commit()
    db.refresh(booking)
    return BookingRead.model_validate(booking)


@router.delete(
    "/waitlist_entries/{waitlist_entry_id}/claim",
    response_model=WaitlistEntryRead,
    summary="Decline the claim offered to you",
    description=(
        "Gives the claim up without taking it, releasing the car immediately rather "
        "than making everyone behind you wait for the expiry. Your waitlist entry "
        "stays visible as a record of what happened, with `state: declined`, but it "
        "is out of the queue — join again if you change your mind.\n\n"
        "Refused if there is no live claim to decline, and the message says why."
    ),
    responses={
        404: {"description": "Waitlist entry not found."},
        409: {"description": "There is no live claim on this entry."},
    },
)
def decline_claim(
    entry: WaitlistEntry = Depends(get_own_waitlist_entry_or_404),
    db: Session = Depends(get_db),
) -> WaitlistEntryRead:
    db.execute(
        select(VehicleClass.id)
        .where(VehicleClass.id == entry.vehicle_class_id)
        .with_for_update()
    )
    _require_live_claim(db, entry)

    entry.declined_at = now()
    db.flush()

    db.commit()
    db.refresh(entry)
    return _read(db, entry)
