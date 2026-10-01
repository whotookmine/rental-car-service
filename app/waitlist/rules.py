"""Waitlist rules that need the database.

One home for queue order, because tickets 44 to 46 all depend on it meaning exactly
one thing: the order people joined, and nothing else. The requirement says strict
FIFO, which rules out "whoever asks first" and "whoever notices first".
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bookings.rules import measure_room
from app.core.clock import now, today
from app.providers.models import Provider
from app.vehicle_classes.models import VehicleClass
from app.waitlist.models import WaitlistEntry


def queue_in_order(
    db: Session,
    vehicle_class_id: int,
    start_date: date,
    end_date: date,
) -> list[WaitlistEntry]:
    """Every entry in one queue, front first.

    Ordered by the joining instant and then by id. The id is not decoration: two
    entries written in the same microsecond would otherwise come back in whatever
    order PostgreSQL liked, and that order would change between runs -- which for a
    queue whose whole promise is "strict FIFO" would be a silent lottery.
    """
    return list(
        db.scalars(
            select(WaitlistEntry)
            .where(
                WaitlistEntry.vehicle_class_id == vehicle_class_id,
                WaitlistEntry.start_date == start_date,
                WaitlistEntry.end_date == end_date,
            )
            .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
        )
        .unique()
        .all()
    )


def position_of(db: Session, entry: WaitlistEntry) -> int:
    """Where this entry stands in its queue, 1 being the front.

    Counted rather than stored. A stored position would have to be rewritten for
    everyone behind anyone who leaves, and the first missed update would leave two
    people believing they were third. Counting cannot drift.

    Note the tuple comparison: an entry ahead is one with an earlier instant, or
    the same instant and a lower id. That is exactly the ordering `queue_in_order`
    uses, so a position can never disagree with the list it came from.
    """
    ahead = db.scalar(
        select(func.count())
        .select_from(WaitlistEntry)
        .where(
            WaitlistEntry.vehicle_class_id == entry.vehicle_class_id,
            WaitlistEntry.start_date == entry.start_date,
            WaitlistEntry.end_date == entry.end_date,
            func.row(WaitlistEntry.created_at, WaitlistEntry.id)
            < func.row(entry.created_at, entry.id),
        )
    )
    return (ahead or 0) + 1


def is_active(entry: WaitlistEntry) -> bool:
    """False once the wanted range has passed.

    A whole queue goes inert together, because the range is part of the queue's
    identity: if the range has gone, it has gone for everyone in it. `today()` from
    the business timezone, like every other date comparison here.
    """
    return entry.end_date >= today()


def offer_released_capacity(
    db: Session,
    vehicle_class_id: int,
) -> WaitlistEntry | None:
    """Offer newly freed capacity to whoever has waited longest and can use it.

    Called after a booking is deleted, inside the same transaction and **under the
    vehicle class row lock already taken by the caller**. Without that lock two
    simultaneous cancellations would both read the same queue, both find the same
    person at the front, and both offer them capacity -- so one car would be
    promised twice and the second person in the queue would never hear anything.

    Strict FIFO, and strictly that: candidates are ordered by when they joined and
    by nothing else. Not by who asked, not by who is watching, and not by whose
    range is the best fit. The requirement is explicit, and "the best fit first"
    would be a defensible policy that is not the one that was asked for.

    An entry is a candidate when all three hold:

    - **It has not already been offered.** This is what makes two cancellations in
      quick succession reach the first and then the second person, rather than both
      reaching the first.
    - **Its range has not passed.** A car freed for days that have gone is no use
      to anyone, and the requirement says such entries are never offered.
    - **Its range now has room.** This is the honest reading of "the first entry
      whose date range the freed capacity satisfies": rather than compare date
      ranges and guess, ask the one function that knows -- if the class is no longer
      full over that entry's range, the release is usable by that entry.

    An entry that fails only the third test is **skipped without losing its place**:
    it is not marked, not moved and not recorded as passed over, so the next release
    considers it again in exactly the same position. That falls out of computing
    candidacy rather than storing it.

    Returns the entry that was offered, or None when nobody in the queue can use
    what was freed -- in which case the capacity simply becomes available to anyone,
    which is what the requirement asks for.
    """
    waiting = db.scalars(
        select(WaitlistEntry)
        .where(
            WaitlistEntry.vehicle_class_id == vehicle_class_id,
            WaitlistEntry.offered_at.is_(None),
            # Inert entries are never offered. Compared through `today()`, in the
            # business timezone, like every other date rule here.
            WaitlistEntry.end_date >= today(),
        )
        .order_by(WaitlistEntry.created_at, WaitlistEntry.id)
    ).unique().all()

    for entry in waiting:
        room = measure_room(db, vehicle_class_id, entry.start_date, entry.end_date)
        if room.is_full:
            # Still nothing for this one. Left completely untouched, so its place
            # in the queue is exactly what it was.
            continue
        entry.offered_at = now()
        db.flush()
        return entry

    return None


def ensure_class_is_full(
    db: Session,
    vehicle_class: VehicleClass,
    start_date: date,
    end_date: date,
) -> None:
    """Refuse to queue someone for a class that is not actually full.

    A waitlist is for when you cannot have the thing. If the class has room, the
    answer is not a place in a queue but a booking, and saying so is more use than
    silently accepting an entry that would be offered capacity it could have taken
    immediately.

    Measured with the same arithmetic booking uses -- vehicles, minus those off the
    road, against the busiest day -- so "full" means here exactly what it means
    there. The lock is taken by the caller before this runs.
    """
    room = measure_room(db, vehicle_class.id, start_date, end_date)
    if not room.is_full:
        free = room.available - room.peak_bookings
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Vehicle class '{vehicle_class.name}' is not full between "
                f"{start_date} and {end_date}: {free} of its vehicles "
                f"{'is' if free == 1 else 'are'} still free. Book it rather than "
                "joining the waitlist."
            ),
        )


def refuse_duplicate_place(
    db: Session,
    *,
    user_id: int,
    vehicle_class: VehicleClass,
    start_date: date,
    end_date: date,
) -> None:
    """Refuse a second place in a queue the caller is already in.

    The unique constraint is the guarantee; this lookup exists so the ordinary case
    gets a sentence a person can read rather than a database error.
    """
    existing = db.scalar(
        select(WaitlistEntry.id).where(
            WaitlistEntry.user_id == user_id,
            WaitlistEntry.vehicle_class_id == vehicle_class.id,
            WaitlistEntry.start_date == start_date,
            WaitlistEntry.end_date == end_date,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"You are already on the waitlist for '{vehicle_class.name}' "
                f"between {start_date} and {end_date}. Joining twice would not "
                "move you up the queue."
            ),
        )


def resolve_class_for_provider(
    db: Session, provider: Provider, vehicle_class_id: int
) -> VehicleClass:
    """Find the class being queued for, and refuse it if it is not this provider's.

    The same two refusals, for the same two different mistakes, that booking makes:
    422 for a class that does not exist (a bad value in the body, not a missing
    path resource) and 409 for one belonging to someone else.
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
