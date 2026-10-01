"""Shared blackout window lookups.

Depends on `get_current_user` for the same reason every other lookup in this
service does: a parameter dependency otherwise resolves ahead of the route's own
auth dependency, and an anonymous caller could read the status code to learn which
identifiers exist.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.blackout_windows.models import BlackoutWindow
from app.db.session import get_db


def get_blackout_window_or_404(
    # Bounded to what an integer primary key can hold, so a larger number answers
    # 404 rather than reaching PostgreSQL and surfacing as a 500.
    blackout_window_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> BlackoutWindow:
    """Resolve the `blackout_window_id` path parameter, or answer 404."""
    window = db.get(BlackoutWindow, blackout_window_id)
    if window is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blackout window not found.",
        )
    return window
