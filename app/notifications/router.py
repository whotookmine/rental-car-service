"""Notifications: what the system has told you, and marking that you have seen it.

**There is no route that creates one**, and that is a rule rather than an omission.
A notification exists to tell a user something the *system* determined; if a client
could post one, it could post one to another user, and the record would no longer
mean anything. The only writer is `notify()` in `app/notifications/service.py`,
which features call in-process.

**Scope never widens for an admin here.** Every other collection in this service
shows an admin more: `GET /bookings` returns everyone's. This one does not, because
a notification is addressed to a person rather than being a record of business
anyone may audit. An admin calling these routes sees their own notifications, which
in practice is an empty list.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.clock import now
from app.db.session import get_db
from app.notifications.dependencies import get_own_notification_or_404
from app.notifications.models import Notification
from app.notifications.schemas import NotificationRead

router = APIRouter(tags=["notifications"])


@router.get(
    "/notifications",
    response_model=list[NotificationRead],
    summary="List your notifications, newest first",
    description=(
        "Returns the calling user's own notifications and nobody else's, newest "
        "first. A user with none receives an empty list, not an error. This route "
        "does not widen for an admin: an admin sees their own, which is normally "
        "none."
    ),
)
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Notification]:
    # Scoped from the token, with no parameter a caller could pass to widen it.
    #
    # Ordered by instant then by id, both descending. The id is not decoration: two
    # notifications written in the same transaction can carry timestamps a
    # microsecond apart or, if a clock is coarse, identical ones, and without a
    # tiebreak PostgreSQL would return them in whatever order it liked and that
    # order would change between runs.
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == current_user.id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
        ).all()
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationRead,
    status_code=status.HTTP_200_OK,
    summary="Mark a notification read",
    description=(
        "Records that you have seen it, and returns the notification. **Idempotent:** "
        "marking an already-read notification answers 200 and leaves the original "
        "`read_at` alone, because the question it records is when you first saw "
        "this, and a retried request must not rewrite that. There is no way to mark "
        "one unread: that would be a record of nothing."
    ),
    responses={404: {"description": "Notification not found."}},
)
def mark_notification_read(
    notification: Notification = Depends(get_own_notification_or_404),
    db: Session = Depends(get_db),
) -> Notification:
    if notification.read_at is None:
        notification.read_at = now()
        db.commit()
        db.refresh(notification)
    return notification
