"""Booking rules that need the database, and so cannot live in a schema.

The date rules are shape rules and belong on the request schema, where they
answer 422. The cap is different: it depends on what else is already stored, so
the request is well formed and the *state* is wrong. That is a 409.

This is the one home for the cap. It takes an owner rather than reading the
caller, because an admin editing someone else's booking must be measured against
that booking's owner, not against themselves.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bookings.models import Booking
from app.core.clock import today

MAX_ACTIVE_BOOKINGS = 3


def count_active_bookings(db: Session, user_id: int) -> int:
    """How many active bookings a user holds.

    A booking is active while its rental period has not ended, so one ending
    today still counts and one that ended yesterday does not. `today` comes from
    the business timezone, never the system clock: seven hours from UTC is enough
    to move a booking across the boundary for part of every day.
    """
    return (
        db.scalar(
            select(func.count())
            .select_from(Booking)
            .where(Booking.user_id == user_id, Booking.end_date >= today())
        )
        or 0
    )


def too_many_active_bookings() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"You already hold {MAX_ACTIVE_BOOKINGS} active bookings. "
            "Delete one, or wait for a rental period to end, before booking again."
        ),
    )


def ensure_room_for_another_booking(db: Session, user_id: int) -> None:
    """Raise 409 if the owner is already at the cap."""
    if count_active_bookings(db, user_id) >= MAX_ACTIVE_BOOKINGS:
        raise too_many_active_bookings()
