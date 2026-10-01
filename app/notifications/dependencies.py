"""Notification lookup, scoped to the caller.

The 404-not-403 rule, the same one bookings use: a notification belonging to
someone else answers exactly as one that does not exist, so identifiers cannot be
walked to discover how much the system has to say to other people.

**No admin widening.** Bookings deliberately widen for an admin, who has to support
customers. A notification is addressed to one person; reading other people's
messages is not oversight, and an admin reaching for one gets the same 404 a
registered user does. `docs/SPEC.md` records the contrast.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.notifications.models import Notification


def get_own_notification_or_404(
    # Bounded to what an integer primary key can hold, so a larger number answers
    # 404 rather than reaching PostgreSQL and surfacing as a 500.
    notification_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Notification:
    """Resolve the path parameter to one of the caller's own, or answer 404."""
    notification = db.get(Notification, notification_id)
    # The ownership test and the existence test share one answer on purpose.
    if notification is None or notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    return notification
