"""Blackout window rules that need the database.

One home for the overlap rule, because ticket 41 will ask the same question from
the booking path -- "is this car off the road on these days?" -- and a rule
enforced in two places drifts, as the password rule did.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.blackout_windows.models import BlackoutWindow
from app.vehicle_classes.models import VehicleClass
from app.vehicles.models import Vehicle


def overlapping_windows(
    db: Session,
    vehicle_id: int,
    start_date: date,
    end_date: date,
    *,
    excluding_id: int | None = None,
) -> list[BlackoutWindow]:
    """Every window on this car that shares at least one day with the period.

    Two inclusive periods overlap when each starts on or before the other ends.
    Stated the other way round, which is the boundary worth being explicit about:
    a window ending on the 5th does **not** overlap one starting on the 6th, and a
    window of a single day overlaps only periods containing that very day.
    """
    stmt = select(BlackoutWindow).where(
        and_(
            BlackoutWindow.vehicle_id == vehicle_id,
            BlackoutWindow.start_date <= end_date,
            BlackoutWindow.end_date >= start_date,
        )
    )
    if excluding_id is not None:
        # Re-dating a window must not collide with itself, or no window could
        # ever be edited.
        stmt = stmt.where(BlackoutWindow.id != excluding_id)
    return list(db.scalars(stmt).unique().all())


def ensure_no_overlap(
    db: Session,
    vehicle: Vehicle,
    start_date: date,
    end_date: date,
    *,
    excluding_id: int | None = None,
) -> None:
    """Refuse a window that shares a day with an existing one on the same car.

    **Refused, not merged.** Both were available and the ticket asked for a
    choice. Merging would silently answer a different request from the one that
    was sent: an admin asking for the 10th to the 12th would be told 201 and find
    a window from the 1st to the 20th, and the two service visits that produced
    them would have become one record that matches neither. Refusing says what is
    in the way and leaves the admin to widen the existing window or cancel it,
    both of which this surface supports.

    The lock comes first, on the vehicle row, for the same reason the capacity
    rule locks the vehicle class: checking and then inserting is a race, and two
    admins scheduling overlapping windows at the same moment would otherwise both
    find the way clear. The exclusion constraint on the table is the real
    guarantee -- it holds even if some later caller forgets this function -- and
    this check exists so the ordinary case gets a sentence a human can read
    instead of an IntegrityError.

    **Two locks, in a fixed order: the vehicle class, then the vehicle.**

    The class row is not locked for this function's own sake -- nothing here reads
    the class. It is locked because `ensure_class_has_room` locks it when a booking
    counts how many cars are free, and since ticket 41 that count includes cars off
    the road for maintenance. Without contending on the same row, a booking could
    read "one car free, none in the workshop" at the same moment this function
    inserts the window that makes that false, and the booking would be accepted on
    a reading that was already stale. A booking cannot lock the vehicle instead: it
    names a class, not a car, and has no way to know which vehicle to lock.

    The order is owner, then vehicle class, then vehicle, on every path that takes
    more than one. Two paths taking the same rows in opposite orders is how a
    deadlock is built, and PostgreSQL would resolve it by killing one caller's
    transaction at random.
    """
    db.execute(
        select(VehicleClass.id)
        .where(VehicleClass.id == vehicle.vehicle_class_id)
        .with_for_update()
    )
    db.execute(select(Vehicle.id).where(Vehicle.id == vehicle.id).with_for_update())

    clash = overlapping_windows(
        db, vehicle.id, start_date, end_date, excluding_id=excluding_id
    )
    if clash:
        existing = clash[0]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Vehicle '{vehicle.plate}' already has a blackout window from "
                f"{existing.start_date} to {existing.end_date}, which overlaps "
                f"{start_date} to {end_date}. Windows on one vehicle may not "
                "overlap: widen or cancel the existing window instead."
            ),
        )
