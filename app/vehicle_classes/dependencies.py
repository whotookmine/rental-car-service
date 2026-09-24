"""Shared vehicle class lookups.

Like `get_provider_or_404`, this depends on `get_current_user` so that an
unauthenticated caller is turned away with 401 before any lookup happens. A
parameter dependency otherwise resolves ahead of the route's own auth dependency,
and an anonymous caller could read the status code to learn which identifiers
exist.

It finds classes under retired providers too. Retirement stops new bookings; it
does not hide the record, and a user must still be able to see what they rented.
"""

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.vehicle_classes.models import VehicleClass


def vehicle_class_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Vehicle class not found.",
    )


def get_vehicle_class_or_404(
    # Bounded to what an integer primary key can hold, so that a larger number
    # answers 404 rather than reaching PostgreSQL and raising
    # NumericValueOutOfRange, which would surface as a 500.
    vehicle_class_id: int = Path(ge=1, le=2147483647),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> VehicleClass:
    """Resolve the `vehicle_class_id` path parameter, or answer 404."""
    vehicle_class = db.get(VehicleClass, vehicle_class_id)
    if vehicle_class is None:
        raise vehicle_class_not_found()
    return vehicle_class
