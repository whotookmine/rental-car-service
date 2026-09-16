"""Shared provider lookups.

`db.get(Provider, ...)` followed by a 404 was written out once per route until it
appeared six times across two packages. One rule, one home: every route that
addresses a provider by identifier resolves it through here, so the not-found
answer cannot drift between them.

This deliberately finds retired providers too. Retirement stops new bookings, it
does not hide the record — users must still be able to see who they booked with.
Routes that need to refuse a retired provider check `is_retired` themselves.

It depends on `get_current_user` so that an unauthenticated caller is always
turned away with 401 before any lookup happens. Without that, a parameter
dependency resolves ahead of the route's own auth dependency and an anonymous
caller can learn which provider identifiers exist by reading the status code.
Ordering the parameters differently would also work and would break the moment
someone reordered them.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.providers.models import Provider


def get_provider_or_404(
    provider_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Provider:
    """Resolve the `provider_id` path parameter, or answer 404."""
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found.",
        )
    return provider
