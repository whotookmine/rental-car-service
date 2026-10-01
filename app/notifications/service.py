"""Writing notifications.

**The only way a notification is ever created.** There is no route that does it,
by design, so this function is what a feature calls when it has something to tell
someone -- the waitlist in tickets 43 to 46 being the first.

It is a plain function rather than a route for the reason the ticket gives: if a
caller could post a notification, a caller could post one to somebody else, and a
record whose provenance is "whoever asked" is not a record of anything. Keeping
the only writer inside the process means every notification in the table was
written by a rule, and the rule is readable.

`db.flush()` rather than `db.commit()`: a notification is almost always part of
something larger -- a cancellation that releases a car both frees the booking and
tells the next person in the queue -- and those must land together or not at all.
Committing here would publish a notification about a transaction that could still
roll back, telling someone their car is ready when it is not. The caller commits.
"""

from sqlalchemy.orm import Session

from app.core.clock import now
from app.notifications.models import Notification, NotificationKind


def notify(
    db: Session,
    *,
    user_id: int,
    kind: NotificationKind | str,
    message: str,
) -> Notification:
    """Record something to tell one user. Flushes; does not commit."""
    notification = Notification(
        user_id=user_id,
        kind=str(kind),
        message=message,
        # From the one clock helper, never datetime.now(): the service runs seven
        # hours from UTC and a notification stamped by the system clock would sort
        # inconsistently against one stamped by a rule.
        created_at=now(),
    )
    db.add(notification)
    db.flush()
    return notification
