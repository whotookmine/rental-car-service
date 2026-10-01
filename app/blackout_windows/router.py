"""Maintenance blackout windows: when each car is off the road.

Reading is open to any authenticated user; scheduling is admin-only. That split is
the ticket's, and it is the right way round: a renter has a legitimate interest in
knowing a car is off the road, and no business deciding when it goes in for
service.

The renter-facing expression of this is not here, though. A renter books a kind of
car, not a particular one, so what they actually need is for availability to stop
counting cars that are in the workshop -- which is ticket 40, and ticket 41 then
refuses the bookings that availability says are impossible. These routes are the
schedule those two read.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.blackout_windows.dependencies import get_blackout_window_or_404
from app.blackout_windows.models import BlackoutWindow
from app.blackout_windows.rules import ensure_no_overlap
from app.blackout_windows.schemas import (
    BlackoutWindowCreate,
    BlackoutWindowRead,
    BlackoutWindowUpdate,
)
from app.db.session import get_db
from app.vehicles.dependencies import get_vehicle_or_404
from app.vehicles.models import Vehicle

router = APIRouter(tags=["maintenance"])

_OVERLAP = (
    "The vehicle already has a blackout window overlapping those dates. Windows "
    "on one vehicle may not overlap."
)

# As everywhere else in this service, `require_admin` is declared before the
# lookup dependencies on the write routes: FastAPI resolves parameter dependencies
# in order, so a lookup first would answer 404 for something that does not exist
# before checking whether the caller is allowed to ask at all.


@router.get(
    "/vehicles/{vehicle_id}/blackout_windows",
    response_model=list[BlackoutWindowRead],
    summary="List a vehicle's blackout windows (authenticated)",
    description=(
        "Every maintenance window scheduled on this car, past and future, "
        "earliest first. Readable by any authenticated user: that a car is off "
        "the road is not confidential, and a renter who has been refused has a "
        "right to see why."
    ),
    responses={404: {"description": "Vehicle not found."}},
)
def list_blackout_windows(
    vehicle: Vehicle = Depends(get_vehicle_or_404),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BlackoutWindow]:
    # Ordered explicitly: without it PostgreSQL returns rows in whatever order it
    # likes, and that order changes between runs.
    return list(
        db.scalars(
            select(BlackoutWindow)
            .where(BlackoutWindow.vehicle_id == vehicle.id)
            .order_by(BlackoutWindow.start_date, BlackoutWindow.id)
        )
        .unique()
        .all()
    )


@router.get(
    "/blackout_windows/{blackout_window_id}",
    response_model=BlackoutWindowRead,
    summary="Fetch a blackout window (authenticated)",
    responses={404: {"description": "Blackout window not found."}},
)
def get_blackout_window(
    window: BlackoutWindow = Depends(get_blackout_window_or_404),
) -> BlackoutWindow:
    return window


@router.post(
    "/vehicles/{vehicle_id}/blackout_windows",
    response_model=BlackoutWindowRead,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a blackout window on a vehicle (admin only)",
    description=(
        "Takes one car off the road for a period, counted inclusively: a window "
        "whose start and end dates are equal is one day. A window may be "
        "scheduled wholly in the past, so that a service that already happened "
        "can be recorded, and there is no maximum length -- a car can be off the "
        "road for months. Two windows on the same car may not overlap."
    ),
    responses={
        403: {"description": "Admin access required."},
        404: {"description": "Vehicle not found."},
        409: {"description": _OVERLAP},
        422: {"description": "end_date is before start_date."},
    },
)
def create_blackout_window(
    payload: BlackoutWindowCreate,
    _admin: User = Depends(require_admin),
    vehicle: Vehicle = Depends(get_vehicle_or_404),
    db: Session = Depends(get_db),
) -> BlackoutWindow:
    ensure_no_overlap(db, vehicle, payload.start_date, payload.end_date)

    window = BlackoutWindow(
        vehicle_id=vehicle.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    db.add(window)
    try:
        db.commit()
    except IntegrityError:
        # The exclusion constraint caught what the check above could not see.
        # Reachable only if a caller reaches the table without taking the lock.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_OVERLAP
        ) from None
    db.refresh(window)
    return window


@router.put(
    "/blackout_windows/{blackout_window_id}",
    response_model=BlackoutWindowRead,
    summary="Change the dates of a blackout window (admin only)",
    description=(
        "Replaces the period. The same shape rule applies as on creation: end on "
        "or after start. The vehicle cannot be changed -- sending it is refused, "
        "not ignored -- because a window records what happened to a particular "
        "car. Cancel it and schedule one on the right car instead."
    ),
    responses={
        403: {"description": "Admin access required."},
        404: {"description": "Blackout window not found."},
        409: {"description": _OVERLAP},
        422: {"description": "end_date is before start_date, or vehicle_id was sent."},
    },
)
def update_blackout_window(
    payload: BlackoutWindowUpdate,
    _admin: User = Depends(require_admin),
    window: BlackoutWindow = Depends(get_blackout_window_or_404),
    db: Session = Depends(get_db),
) -> BlackoutWindow:
    ensure_no_overlap(
        db,
        window.vehicle,
        payload.start_date,
        payload.end_date,
        # The window being moved must not be found as its own obstacle, or no
        # window could ever be edited.
        excluding_id=window.id,
    )

    window.start_date = payload.start_date
    window.end_date = payload.end_date
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_OVERLAP
        ) from None
    db.refresh(window)
    return window


@router.delete(
    "/blackout_windows/{blackout_window_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a blackout window (admin only)",
    description=(
        "Removes the window outright: the car is back on the road from that "
        "moment, and there is no cancelled state to inspect. Nothing references a "
        "window, so this never conflicts."
    ),
    responses={
        403: {"description": "Admin access required."},
        404: {"description": "Blackout window not found."},
    },
)
def delete_blackout_window(
    _admin: User = Depends(require_admin),
    window: BlackoutWindow = Depends(get_blackout_window_or_404),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(window)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
