"""Booking rules that need the database, and so cannot live in a schema.

The date rules are shape rules and belong on the request schema, where they
answer 422. The cap and the retired-provider guard are different: the request is
well formed and the *state* is wrong. That is a 409.

This is the one home for these rules. The cap takes an owner rather than reading
the caller, because an admin editing someone else's booking must be measured
against that booking's owner, not against themselves.
"""

from datetime import date
from typing import NamedTuple

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.models import User
from app.blackout_windows.models import BlackoutWindow
from app.bookings.models import Booking
from app.branches.models import Branch
from app.core.clock import now, today
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
# What the busiest single day of a requested period costs, measured per day rather
# than per booking. Two bookings that share one day both consume a car that day,
# even if they differ on every other day, so a whole-period count would let a class
# be over-booked by bookings that merely fail to nest.
#
# **Two things occupy a car, not one.** A booking does, obviously. A live waitlist
# claim does too: ticket 45 holds released capacity for the person it was offered to,
# so while that claim stands the car is not available to anyone else even though it
# is physically free. Counting them together in one per-day figure is what makes
# "full" mean the same thing to a renter, to availability, and to the queue.
#
# A claim is live when it has been offered, has not been converted or declined, and
# has not passed its expiry. Expiry is judged against the instant passed in rather
# than `now()` inside the SQL, so that every row in one request is measured against
# one consistent moment -- a query that read the clock per row could count a claim as
# live and dead in the same answer.
#
# `generate_series` walks the requested days one at a time. That is the simplest
# thing that is obviously correct, and the series is bounded: a rental period is at
# most thirty days by the schema rule, so this is at most thirty rows.
_PEAK_OCCUPANCY_ON_ANY_DAY = text(
    """
    SELECT COALESCE(MAX(taken), 0) FROM (
        SELECT (
            (SELECT COUNT(*)
               FROM bookings b
              WHERE b.vehicle_class_id = :vehicle_class_id
                AND b.start_date <= d.day
                AND b.end_date >= d.day
                AND (CAST(:excluding_booking_id AS integer) IS NULL
                     OR b.id <> CAST(:excluding_booking_id AS integer)))
            +
            (SELECT COUNT(*)
               FROM waitlist_entries w
              WHERE w.vehicle_class_id = :vehicle_class_id
                AND w.start_date <= d.day
                AND w.end_date >= d.day
                AND w.offered_at IS NOT NULL
                AND w.converted_at IS NULL
                AND w.declined_at IS NULL
                AND w.claim_expires_at > CAST(:at AS timestamptz)
                AND (CAST(:excluding_claim_entry_id AS integer) IS NULL
                     OR w.id <> CAST(:excluding_claim_entry_id AS integer)))
        ) AS taken
        FROM generate_series(
                 CAST(:start_date AS date),
                 CAST(:end_date AS date),
                 CAST('1 day' AS interval)
             ) AS d(day)
    ) per_day
    """
)


def count_vehicles_in_class(db: Session, vehicle_class_id: int) -> int:
    """How many cars sit in a class, whether or not they are on the road."""
    return (
        db.scalar(
            select(func.count())
            .select_from(Vehicle)
            .where(Vehicle.vehicle_class_id == vehicle_class_id)
        )
        or 0
    )


def count_blacked_out_vehicles(
    db: Session, vehicle_class_id: int, start_date: date, end_date: date
) -> int:
    """How many of a class's cars are off the road for part of the period.

    A car is out for the whole period if a blackout window covers even one day of
    it: a car that must be handed back to the workshop midway through is not a car
    you can rent for the period. That is the same rule availability applies, which
    is what makes the two answers agree.

    Inclusive overlap on both sides, so a window ending the day before the period
    starts costs nothing, and one starting on the period's final day costs a car.
    """
    return (
        db.scalar(
            select(func.count(func.distinct(Vehicle.id)))
            .select_from(Vehicle)
            .join(BlackoutWindow, BlackoutWindow.vehicle_id == Vehicle.id)
            .where(
                Vehicle.vehicle_class_id == vehicle_class_id,
                BlackoutWindow.start_date <= end_date,
                BlackoutWindow.end_date >= start_date,
            )
        )
        or 0
    )


class ClassRoom(NamedTuple):
    """How much room a vehicle class has over one period, and why.

    One home for this arithmetic. Three callers need it and need it to agree:
    `ensure_class_has_room` refuses a booking, `GET /providers/{id}/availability`
    reports a count, and the waitlist refuses to queue someone for a class that is
    not actually full. Ticket 40 left availability and booking computing the same
    thing in two places and they immediately disagreed; a third copy would have
    been worse.
    """

    total: int
    blacked_out: int
    available: int
    # Bookings *and* live claims. Named occupancy rather than bookings since ticket
    # 45, because a claim takes a car out of circulation just as a booking does.
    peak_occupancy: int

    @property
    def is_full(self) -> bool:
        """True when nothing more can be booked over the period."""
        return self.peak_occupancy >= self.available


def measure_room(
    db: Session,
    vehicle_class_id: int,
    start_date: date,
    end_date: date,
    *,
    excluding_booking_id: int | None = None,
    excluding_claim_entry_id: int | None = None,
) -> ClassRoom:
    """Count vehicles, maintenance, bookings and live claims over one period.

    Does **not** lock. A caller that is about to write on the strength of the
    answer must take the vehicle class row lock first -- see
    `ensure_class_has_room` -- and a caller that is only reporting need not.

    `excluding_claim_entry_id` leaves one waitlist entry's own claim out of the
    count. Converting a claim needs it: the holder must be able to book the very
    car their claim is holding, which is the whole point of an exclusive claim, and
    without this they would be refused by their own reservation.
    """
    total = count_vehicles_in_class(db, vehicle_class_id)
    blacked_out = count_blacked_out_vehicles(
        db, vehicle_class_id, start_date, end_date
    )
    peak = (
        db.scalar(
            _PEAK_OCCUPANCY_ON_ANY_DAY,
            {
                "start_date": start_date,
                "end_date": end_date,
                "vehicle_class_id": vehicle_class_id,
                "excluding_booking_id": excluding_booking_id,
                "excluding_claim_entry_id": excluding_claim_entry_id,
                # One instant for the whole measurement, from the one clock helper.
                "at": now(),
            },
        )
        or 0
    )
    # Never negative: a car can be counted out only once, but clamping keeps the
    # arithmetic honest if that ever stops being true.
    return ClassRoom(
        total=total,
        blacked_out=blacked_out,
        available=max(0, total - blacked_out),
        peak_occupancy=peak,
    )


def _refusal(
    *,
    name: str,
    start_date: date,
    end_date: date,
    total: int,
    blacked_out: int,
    available: int,
) -> HTTPException:
    """The 409, worded so the caller knows whether waiting will help.

    Three different situations hide behind "you cannot have this car", and the
    remedy differs in each. Telling them apart is the whole point of this
    function:

    - **No cars at all.** Nothing to wait for and nothing to re-date to.
    - **Every car off the road for maintenance.** No cancellation can help,
      because the cars are not in anyone else's hands -- they are in the workshop.
      Different dates might.
    - **Fully booked.** Someone else is holding the car, so a cancellation does
      free it, which is exactly what the waitlist in ticket 43 will queue for.

    The mixed case says both, because the caller needs to know that part of the
    shortfall will never be released however long they wait.
    """
    if total == 0:
        detail = (
            f"Vehicle class '{name}' cannot be booked between {start_date} and "
            f"{end_date}: it has no vehicles."
        )
    elif available == 0:
        # Every car in the class is in the workshop for part of the period.
        fleet = (
            "its only vehicle is"
            if total == 1
            else f"all {total} of its vehicles are"
        )
        detail = (
            f"Vehicle class '{name}' cannot be booked between {start_date} and "
            f"{end_date}: {fleet} off the road for maintenance for part of that "
            "period. Waiting will not free one, because no other booking is "
            "holding them; try different dates."
        )
    elif blacked_out:
        # Partly maintenance, partly demand.
        detail = (
            f"Vehicle class '{name}' is fully booked between {start_date} and "
            f"{end_date}. {blacked_out} of its {total} vehicles are off the road "
            f"for maintenance for part of that period, and the {available} still "
            "on the road are taken on at least one of those days."
        )
    else:
        # The original ticket 26 wording, unchanged: no maintenance is involved,
        # so the sentence a caller already knows should not move under them.
        detail = f"Vehicle class '{name}' is fully booked between {start_date} and {end_date}. " + (
            "Its only vehicle is taken on at least one of those days."
            if total == 1
            else f"All {total} of its vehicles are taken on at least one of those days."
        )

    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def ensure_class_has_room(
    db: Session,
    vehicle_class: VehicleClass,
    start_date: date,
    end_date: date,
    *,
    excluding_booking_id: int | None = None,
    excluding_claim_entry_id: int | None = None,
) -> None:
    """Raise 409 unless the class has a car that is both free and on the road.

    Capacity is counted three ways at once, because all three reduce it and a
    caller hitting the limit needs to know which:

        available = vehicles in the class - vehicles off the road for maintenance
        refused when the busiest day of the period already has `available`
        bookings on it

    So two vehicles with one blacked out and one already booked is a full class,
    even though neither count alone reaches two. This is the same arithmetic
    `GET /providers/{id}/availability` performs, which is what makes the two
    answers agree rather than merely tend to.

    The lock comes first, on the **vehicle class** row, for exactly the reason the
    active-booking cap locks the owner: counting and then inserting is a race, and
    two requests can otherwise both see the last car free and both take it.

    **That same row is what scheduling a blackout window locks**, so a booking and
    a maintenance window cannot race either: one of them waits for the other to
    commit and then counts what it did. Locking the vehicle would not have been
    enough -- a booking names a class, not a car, and cannot know which vehicle to
    lock.

    **Lock order matters.** Every path takes owner, then vehicle class, then
    vehicle. Taking them in opposite orders in two different routes is how a
    deadlock is built, and PostgreSQL would resolve it by killing one caller's
    transaction at random.

    A class whose cars have since been sold, or blacked out after the fact, can
    hold more bookings than it now has room for. Those bookings stand -- history is
    never destroyed to satisfy a later rule -- and only new ones are refused.
    """
    db.execute(
        select(VehicleClass.id)
        .where(VehicleClass.id == vehicle_class.id)
        .with_for_update()
    )

    room = measure_room(
        db,
        vehicle_class.id,
        start_date,
        end_date,
        excluding_booking_id=excluding_booking_id,
        excluding_claim_entry_id=excluding_claim_entry_id,
    )
    if room.is_full:
        raise _refusal(
            name=vehicle_class.name,
            start_date=start_date,
            end_date=end_date,
            total=room.total,
            blacked_out=room.blacked_out,
            available=room.available,
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
