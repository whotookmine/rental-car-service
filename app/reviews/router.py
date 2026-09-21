"""Reviews: leaving a rating and comment after a rental ends."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.bookings.dependencies import get_visible_booking_or_404
from app.bookings.models import Booking
from app.core.clock import today
from app.db.session import get_db
from app.reviews.dependencies import get_deletable_review_or_404, get_owned_review_or_404
from app.reviews.models import Review
from app.reviews.schemas import ReviewCreate, ReviewRead, ReviewUpdate

router = APIRouter(tags=["reviews"])


@router.post(
    "/bookings/{booking_id}/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Review a completed booking",
    description=(
        "Creates a review for a booking whose rental period has ended. "
        "Only the booking's owner may review it, and only once."
    ),
    responses={
        404: {"description": "Booking not found."},
        409: {"description": "Rental period has not ended, or booking already reviewed."},
    },
)
def create_review(
    payload: ReviewCreate,
    booking: Booking = Depends(get_visible_booking_or_404),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReviewRead:
    # get_visible_booking_or_404 already returns 404 for a regular user reaching
    # another user's booking. Admins can see any booking but do not own them, so
    # an explicit ownership check is needed to cover that case consistently.
    if booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    # A booking whose rental period ended today counts as ended.
    if booking.end_date >= today():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This booking's rental period has not ended yet. "
                "Reviews can only be written once the rental is complete."
            ),
        )

    review = Review(
        booking_id=booking.id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(review)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This booking has already been reviewed.",
        )

    db.refresh(review)
    return ReviewRead.model_validate(review)


@router.put(
    "/reviews/{review_id}",
    response_model=ReviewRead,
    summary="Edit a review",
    description="Replaces the rating and comment. Only the review's author may edit it.",
    responses={404: {"description": "Review not found."}},
)
def update_review(
    payload: ReviewUpdate,
    review: Review = Depends(get_owned_review_or_404),
    db: Session = Depends(get_db),
) -> ReviewRead:
    review.rating = payload.rating
    review.comment = payload.comment
    db.commit()
    db.refresh(review)
    return ReviewRead.model_validate(review)


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a review",
    description=(
        "Removes the review. The booking is left intact and becomes reviewable again. "
        "The review's author or an admin may delete it."
    ),
    responses={404: {"description": "Review not found."}},
)
def delete_review(
    review: Review = Depends(get_deletable_review_or_404),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(review)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
