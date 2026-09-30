"""Booking rules that need the database, and so cannot live in a schema.

The date rules are shape rules and belong on the request schema, where they
answer 422. The cap and the retired-provider guard are different: the request is
well formed and the *state* is wrong. That is a 409.

This is the one home for these rules. The cap takes an owner rather than reading
the caller, because an admin editing someone else's booking must be measured
against that booking's owner, not against themselves.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.models import User
from app.bookings.models import Booking
from app.branches.models import Branch
from app.core.clock import today
from app.one_way_routes.models import OneWayRoute
from app.reviews.models import Review
from app.providers.models import Provider
from app.vehicle_classes.models import VehicleClass
from app.vehicles.models import Vehicle

MAX_ACTIVE_BOOKINGS = 3

# The busiest single day in a requested rental period, measured per day rather
# than per booking. Two bookings that share one day both consume a car that day,
# even if they differ on every other day, so a whole-period count would let a
# class be over-booked by bookings that merely fail to nest.
#
# `generate_series` walks the requested days one at a time. That is the simplest
# thing that is obviously correct, and the series is bounded: a rental period is
# at most thirty days by the schema rule, so this is at most thirty rows.
_PEAK_BOOKINGS_ON_ANY_DAY = text(
    """
    SELECT COALESCE(MAX(taken), 0) FROM (
        SELECT COUNT(b.id) AS taken
        FROM generate_series(
                 CAST(:start_date AS date),
                 CAST(:end_date AS date),
                 CAST('1 day' AS interval)
             ) AS d(day)
        LEFT JOIN bookings b
               ON b.vehicle_class_id = :vehicle_class_id
              AND b.start_date <= d.day
              AND b.end_date >= d.day
              AND (CAST(:excluding_booking_id AS integer) IS NULL
                   OR b.id <> CAST(:excluding_booking_id AS integer))
        GROUP BY d.day
    ) per_day
    """
)


def count_vehicles_in_class(db: Session, vehicle_class_id: int) -> int:
    """How many cars sit in a class. This is its capacity."""
    return (
        db.scalar(
            select(func.count())
            .select_from(Vehicle)
            .where(Vehicle.vehicle_class_id == vehicle_class_id)
        )
        or 0
    )


def ensure_class_has_room(
    db: Session,
    vehicle_class: VehicleClass,
    start_date: date,
    end_date: date,
    *,
    excluding_booking_id: int | None = None,
) -> None:
    """Raise 409 if every car in the class is taken on any day of the period.

    The lock comes first, on the vehicle class row, for exactly the reason the
    active-booking cap locks the owner: counting and then inserting is a race,
    and two requests can otherwise both see the last car free and both take it.
    Locking the class serialises every booking that changes that class's
    occupancy.

    **Lock order matters.** Every path that takes both locks takes the owner
    first and the class second. Taking them in opposite orders in two different
    routes is how a deadlock is built, and PostgreSQL would resolve it by
    killing one caller's transaction at random.

    A class whose cars have since been sold can hold more bookings than it has
    capacity for. Those bookings stand -- history is never destroyed to satisfy
    a later rule -- and only new ones are refused.
    """
    db.execute(
        select(VehicleClass.id)
        .where(VehicleClass.id == vehicle_class.id)
        .with_for_update()
    )

    capacity = count_vehicles_in_class(db, vehicle_class.id)
    peak = (
        db.scalar(
            _PEAK_BOOKINGS_ON_ANY_DAY,
            {
                "start_date": start_date,
                "end_date": end_date,
                "vehicle_class_id": vehicle_class.id,
                "excluding_booking_id": excluding_booking_id,
            },
        )
        or 0
    )

    if peak >= capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Vehicle class '{vehicle_class.name}' is fully booked between "
                f"{start_date} and {end_date}. "
                + (
                    "This class has no vehicles."
                    if capacity == 0
                    else "Its only vehicle is taken on at least one of those days."
                    if capacity == 1
                    else f"All {capacity} of its vehicles are taken on at least "
                    "one of those days."
                )
            ),
        )


def ensure_provider_is_active(provider: Provider) -> None:
    """Raise 409 if the provider has retired and is no longer accepting bookings."""
    if provider.is_retired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Provider '{provider.name}' has retired and is no longer "
                "accepting bookings. Reinstate the provider before booking."
            ),
        )


def resolve_vehicle_class_for_provider(
    db: Session, provider: Provider, vehicle_class_id: int
) -> VehicleClass:
    """Find the class being booked, and refuse it if it is not this provider's.

    Two different refusals, because they are two different mistakes:

    - A class that does not exist is a bad value in the request body, not a
      missing resource at the path being addressed. That is a 422, matching how
      a vehicle's own edit answers when it names a class that is not there.
    - A class that exists but belongs to someone else is a well-formed request
      against the wrong state. That is a 409, and the message says so plainly,
      because the caller can see both catalogues and needs to know which half of
      the request to change.
    """
    vehicle_class = db.get(VehicleClass, vehicle_class_id)
    if vehicle_class is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Vehicle class not found.",
        )
    if vehicle_class.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Vehicle class '{vehicle_class.name}' does not belong to "
                f"provider '{provider.name}'."
            ),
        )
    return vehicle_class


def resolve_branch_for_provider(
    db: Session, provider: Provider, branch_id: int
) -> Branch:
    """Find the pickup branch, and refuse it if it is not this provider's.

    Same two-refusal logic as `resolve_vehicle_class_for_provider`:

    - A branch that does not exist is a bad body value, not a missing path
      resource. That is a 422.
    - A branch that exists but belongs to a different provider is a well-formed
      request against the wrong state. That is a 409.
    """
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Branch not found.",
        )
    if branch.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Branch '{branch.name}' does not belong to "
                f"provider '{provider.name}'."
            ),
        )
    return branch


def count_active_bookings(
    db: Session, user_id: int, *, excluding_booking_id: int | None = None
) -> int:
    """How many active bookings a user holds.

    A booking is active while its rental period has not ended, so one ending
    today still counts and one that ended yesterday does not. `today` comes from
    the business timezone, never the system clock: seven hours from UTC is enough
    to move a booking across the boundary for part of every day.

    `excluding_booking_id` leaves one booking out. Re-dating needs it: the
    booking being changed must not be counted against itself, or a user holding
    the maximum could never edit any of them.
    """
    stmt = (
        select(func.count())
        .select_from(Booking)
        .where(Booking.user_id == user_id, Booking.end_date >= today())
    )
    if excluding_booking_id is not None:
        stmt = stmt.where(Booking.id != excluding_booking_id)
    return db.scalar(stmt) or 0


def too_many_active_bookings(*, owner_is_caller: bool) -> HTTPException:
    """The refusal, worded for whoever is reading it.

    An admin editing someone else's booking is told about that booking's owner,
    not addressed as though the bookings were theirs. The rule is the same either
    way; only the sentence changes.
    """
    if owner_is_caller:
        subject = f"You already hold {MAX_ACTIVE_BOOKINGS} active bookings."
        remedy = "Delete one, or wait for a rental period to end, before booking again."
    else:
        subject = (
            f"The owner of this booking already holds {MAX_ACTIVE_BOOKINGS} "
            "active bookings."
        )
        remedy = (
            "One of theirs must be deleted, or a rental period must end, before "
            "this booking can be active."
        )

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT, detail=f"{subject} {remedy}"
    )


def ensure_room_for_another_booking(
    db: Session,
    user_id: int,
    *,
    excluding_booking_id: int | None = None,
    owner_is_caller: bool = True,
) -> None:
    """Raise 409 if the owner is already at the cap.

    Counting and then inserting is a race: two requests can both read two active
    bookings and both insert, leaving the owner with four. Locking the owner's
    row first serialises everything that changes that owner's booking count, so
    the second request blocks until the first has committed and then counts the
    row the first one added.

    The lock is taken on the user rather than on the bookings, because the thing
    being protected is a property of the user — how many they hold — and a row
    that does not exist yet cannot be locked. ADR 0001 chose PostgreSQL partly
    for exactly this; the lock is the transaction that decision promised.
    """
    db.execute(select(User.id).where(User.id == user_id).with_for_update())

    if (
        count_active_bookings(db, user_id, excluding_booking_id=excluding_booking_id)
        >= MAX_ACTIVE_BOOKINGS
    ):
        raise too_many_active_bookings(owner_is_caller=owner_is_caller)


def ensure_one_way_route_enabled(
    db: Session,
    pickup_branch: Branch,
    dropoff_branch: Branch,
) -> None:
    """Raise 409 if the provider has not enabled one-way service pickup→dropoff."""
    row = db.get(OneWayRoute, (pickup_branch.id, dropoff_branch.id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"One-way rental from '{pickup_branch.name}' to "
                f"'{dropoff_branch.name}' has not been enabled by this provider."
            ),
        )


def ensure_reviewed_booking_stays_ended(db: Session, booking_id: int, new_end_date) -> None:
    """Refuse an edit that would leave a reviewed booking not yet ended.

    A review describes a finished rental. If a booking that already carries one
    could be re-dated into the future, the table would hold a review of a rental
    still in progress, contradicting the premise reviews are written on.

    The rule belongs to the booking rather than to either role: an owner and an
    admin reach it through the same edit, and it applies to both identically.

    A rental period ending today has not ended — that is the same boundary the
    active-booking cap uses — so moving a reviewed booking to end today is
    refused just as moving it into the future is.
    """
    if new_end_date < today():
        return  # Still ended after the edit; nothing to protect.

    has_review = db.scalar(
        select(func.count()).select_from(Review).where(Review.booking_id == booking_id)
    )
    if has_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This booking has been reviewed, so its rental period cannot be "
                "moved to a date that has not passed. Delete the review first."
            ),
        )
