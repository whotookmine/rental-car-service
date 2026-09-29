"""Shared branch lookups.

Depends on `get_current_user` so that an unauthenticated caller is turned away
with 401 before any lookup happens. A parameter dependency otherwise resolves
ahead of the route's own auth dependency, and an anonymous caller could read the
status code to learn which branch identifiers exist.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.branches.models import Branch
from app.db.session import get_db


def get_branch_or_404(
    branch_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Branch:
    """Resolve the `branch_id` path parameter, or answer 404."""
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found.",
        )
    return branch
