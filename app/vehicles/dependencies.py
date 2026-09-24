"""Shared vehicle lookups.

Depends on `get_current_user` for the same reason `get_provider_or_404` and
`get_vehicle_class_or_404` do: a parameter dependency otherwise resolves ahead of
the route's own auth dependency, and an anonymous caller could read the status
code to learn which identifiers exist.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.vehicles.models import Vehicle


def vehicle_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Vehicle not found.",
    )


def get_vehicle_or_404(
    # Bounded to what an integer primary key can hold, so a larger number answers
    # 404 rather than reaching PostgreSQL and surfacing as a 500.
    vehicle_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Vehicle:
    """Resolve the `vehicle_id` path parameter, or answer 404."""
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise vehicle_not_found()
    return vehicle
