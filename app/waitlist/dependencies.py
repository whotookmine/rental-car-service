"""Waitlist entry lookup, scoped to the caller.

404-not-403, matching bookings: another user's entry answers exactly as one that
does not exist, so entry ids cannot be walked to learn who is waiting for what.

**No admin widening on a single entry.** An admin has no oversight role the queue
needs -- nothing in the requirement asks an admin to manage a waitlist -- and
leaving the scope narrow means the ordering rules have one code path rather than
two.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.waitlist.models import WaitlistEntry


def get_own_waitlist_entry_or_404(
    waitlist_entry_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WaitlistEntry:
    """Resolve the path parameter to one of the caller's own, or answer 404."""
    entry = db.get(WaitlistEntry, waitlist_entry_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Waitlist entry not found.",
        )
    return entry
