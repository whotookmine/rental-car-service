"""Shared booking lookups.

Ownership scoping lives here so that every route enforcing it answers the same
way. A booking that belongs to someone else and a booking that does not exist
are deliberately indistinguishable: both are 404. A 403 would confirm that the
identifier is real and someone else's, which is enough to count how much other
people are renting by walking the identifiers.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.bookings.models import Booking
from app.db.session import get_db


def booking_not_found() -> HTTPException:
    """The one answer for a booking the caller may not see, whatever the reason."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Booking not found.",
    )


def get_own_booking_or_404(
    # Bounded for the same reason as provider ids: a larger number would reach
    # PostgreSQL and raise, turning a promised 404 into a 500.
    booking_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    """Resolve the `booking_id` path parameter, scoped to the calling user."""
    booking = db.get(Booking, booking_id)
    if booking is None or booking.user_id != current_user.id:
        raise booking_not_found()
    return booking
