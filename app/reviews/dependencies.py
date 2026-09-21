"""Shared review lookups.

A review is addressed by its own id, but ownership is through the booking it
belongs to. A review that does not exist and one belonging to another user are
both 404, so that review identifiers cannot be used to learn which bookings other
users have reviewed.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User, UserRole
from app.bookings.models import Booking
from app.db.session import get_db
from app.reviews.models import Review


def _resolve_review(review_id: int, db: Session) -> Review:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    return review


def get_owned_review_or_404(
    review_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Review:
    """Owner-only: editing a review. Admins are refused with 404."""
    review = _resolve_review(review_id, db)
    booking = db.get(Booking, review.booking_id)
    if booking is None or booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    return review


def get_deletable_review_or_404(
    review_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Review:
    """Owner or admin: deleting a review.

    An admin may delete any review; a registered user may only delete their own.
    A registered user reaching another user's review still gets 404.
    """
    review = _resolve_review(review_id, db)
    if current_user.role == UserRole.admin:
        return review
    booking = db.get(Booking, review.booking_id)
    if booking is None or booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found.")
    return review
