"""Shared booking lookups.

Scoping lives here so that every route enforcing it answers the same way. For a
registered user, a booking that belongs to someone else and a booking that does
not exist are deliberately indistinguishable: both are 404. A 403 would confirm
that the identifier is real and someone else's, which is enough to count how much
other people are renting by walking the identifiers.

An admin sees every booking through the same dependency and the same routes.
Scope widens by role rather than through a separate admin namespace, so the
ownership rule exists once and cannot drift between two copies — which is the
usual way an admin route ends up forgetting to check anything at all.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.bookings.models import Booking
from app.db.session import get_db


def booking_not_found() -> HTTPException:
    """The one answer for a booking the caller may not see, whatever the reason."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Booking not found.",
    )


def get_visible_booking_or_404(
    # Bounded for the same reason as provider ids: a larger number would reach
    # PostgreSQL and raise, turning a promised 404 into a 500.
    booking_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    """Resolve the `booking_id` path parameter within the caller's scope.

    A registered user reaches only their own bookings; an admin reaches any.
    """
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise booking_not_found()

    if current_user.role != UserRole.admin and booking.user_id != current_user.id:
        raise booking_not_found()

    return booking
