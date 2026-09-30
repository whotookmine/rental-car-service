"""The vehicle class catalogue: what kinds of car a provider rents out."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.core.config import get_settings
from app.core.money import Money
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider
from app.vehicle_classes.dependencies import get_vehicle_class_or_404
from app.vehicle_classes.models import VehicleClass
from app.vehicle_classes.schemas import (
    VehicleClassCreate,
    VehicleClassRead,
    VehicleClassUpdate,
)
from app.vehicles.models import Vehicle

router = APIRouter(tags=["vehicle classes"])

# As in the provider router, `require_admin` is declared before the lookup
# dependencies on purpose: FastAPI resolves parameter dependencies in the order
# they appear, so putting a lookup first would answer 404 for something that does
# not exist before checking whether the caller is allowed to ask at all.

_DUPLICATE_NAME = "This provider already has a vehicle class with that name."


def _counts_subquery():
    """Subquery counting the cars in each vehicle class.

    Read-time aggregation rather than a stored column, matching how a provider's
    average rating is handled: nothing can drift out of step with the fleet.
    """
    return (
        select(
            Vehicle.vehicle_class_id.label("vehicle_class_id"),
            func.count(Vehicle.id).label("vehicle_count"),
        )
        .group_by(Vehicle.vehicle_class_id)
        .subquery()
    )


def _build_read(vehicle_class: VehicleClass, count: int | None) -> VehicleClassRead:
    currency = get_settings().currency
    daily_rate = (
        Money(amount=vehicle_class.daily_rate, currency=currency)
        if vehicle_class.daily_rate is not None
        else None
    )
    return VehicleClassRead(
        id=vehicle_class.id,
        provider_id=vehicle_class.provider_id,
        name=vehicle_class.name,
        description=vehicle_class.description,
        daily_rate=daily_rate,
        vehicle_count=count or 0,
    )


def _fetch_one(vehicle_class_id: int, db: Session) -> VehicleClassRead:
    counts = _counts_subquery()
    row = db.execute(
        select(VehicleClass, counts.c.vehicle_count)
        .outerjoin(counts, counts.c.vehicle_class_id == VehicleClass.id)
        .where(VehicleClass.id == vehicle_class_id)
    ).one()
    return _build_read(row[0], row[1])


def _duplicate_name() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_NAME)


def _refuse_duplicate_name(
    db: Session, *, provider_id: int, name: str, excluding_id: int | None = None
) -> None:
    """Refuse a name already used by another class under the same provider.

    The unique index is what actually guarantees this; the lookup is here so the
    ordinary case gets a sentence a human can read rather than a database error.
    """
    stmt = select(VehicleClass.id).where(
        VehicleClass.provider_id == provider_id,
        func.lower(VehicleClass.name) == name.lower(),
    )
    if excluding_id is not None:
        stmt = stmt.where(VehicleClass.id != excluding_id)
    if db.execute(stmt).first() is not None:
        raise _duplicate_name()


@router.get(
    "/providers/{provider_id}/vehicle_classes",
    response_model=list[VehicleClassRead],
    summary="List a provider's vehicle classes (authenticated)",
    description=(
        "Returns the kinds of car this provider rents out, ordered by name then "
        "id. Classes under a retired provider are listed too, so a user can still "
        "see what they rented."
    ),
    responses={404: {"description": "Provider not found."}},
)
def list_vehicle_classes(
    provider: Provider = Depends(get_provider_or_404),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VehicleClassRead]:
    counts = _counts_subquery()
    rows = db.execute(
        select(VehicleClass, counts.c.vehicle_count)
        .outerjoin(counts, counts.c.vehicle_class_id == VehicleClass.id)
        .where(VehicleClass.provider_id == provider.id)
        .order_by(VehicleClass.name, VehicleClass.id)
    ).all()
    return [_build_read(row[0], row[1]) for row in rows]


@router.get(
    "/vehicle_classes/{vehicle_class_id}",
    response_model=VehicleClassRead,
    summary="Fetch a single vehicle class (authenticated)",
    responses={404: {"description": "Vehicle class not found."}},
)
def get_vehicle_class(
    vehicle_class: VehicleClass = Depends(get_vehicle_class_or_404),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VehicleClassRead:
    return _fetch_one(vehicle_class.id, db)


@router.post(
    "/providers/{provider_id}/vehicle_classes",
    response_model=VehicleClassRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a vehicle class to a provider (admin only)",
    description=(
        "The class belongs to the provider in the path for its whole life. Names "
        "are unique within a provider, compared without regard to case."
    ),
    responses={
        404: {"description": "Provider not found."},
        409: {"description": _DUPLICATE_NAME},
    },
)
def create_vehicle_class(
    payload: VehicleClassCreate,
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> VehicleClassRead:
    _refuse_duplicate_name(db, provider_id=provider.id, name=payload.name)

    vehicle_class = VehicleClass(
        provider_id=provider.id,
        name=payload.name,
        description=payload.description,
        daily_rate=payload.daily_rate,
    )
    db.add(vehicle_class)
    try:
        db.commit()
    except IntegrityError:
        # Two admins naming the same class at once: the index caught what the
        # lookup above could not see.
        db.rollback()
        raise _duplicate_name() from None
    db.refresh(vehicle_class)
    return _fetch_one(vehicle_class.id, db)


@router.patch(
    "/vehicle_classes/{vehicle_class_id}",
    response_model=VehicleClassRead,
    summary="Edit a vehicle class (admin only)",
    description=(
        "Only the name and the description can change. A class cannot be moved to "
        "another provider."
    ),
    responses={
        404: {"description": "Vehicle class not found."},
        409: {"description": _DUPLICATE_NAME},
    },
)
def update_vehicle_class(
    payload: VehicleClassUpdate,
    _admin: User = Depends(require_admin),
    vehicle_class: VehicleClass = Depends(get_vehicle_class_or_404),
    db: Session = Depends(get_db),
) -> VehicleClassRead:
    if payload.name is not None:
        _refuse_duplicate_name(
            db,
            provider_id=vehicle_class.provider_id,
            name=payload.name,
            excluding_id=vehicle_class.id,
        )
        vehicle_class.name = payload.name
    if payload.description is not None:
        vehicle_class.description = payload.description
    # Use model_fields_set to distinguish "not sent" from "sent as null".
    # Sending null explicitly means "remove the price" (mark unpriced).
    if "daily_rate" in payload.model_fields_set:
        vehicle_class.daily_rate = payload.daily_rate

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _duplicate_name() from None
    db.refresh(vehicle_class)
    return _fetch_one(vehicle_class.id, db)


@router.delete(
    "/vehicle_classes/{vehicle_class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a vehicle class (admin only)",
    description=(
        "Removes the class outright. A class that anything else still points at "
        "is refused with 409 rather than taking its references down with it: "
        "catalogue housekeeping must never destroy history."
    ),
    responses={
        404: {"description": "Vehicle class not found."},
        409: {"description": "Vehicle class is in use and cannot be removed."},
    },
)
def delete_vehicle_class(
    _admin: User = Depends(require_admin),
    vehicle_class: VehicleClass = Depends(get_vehicle_class_or_404),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(vehicle_class)
    try:
        db.commit()
    except IntegrityError:
        # Every table that comes to reference a vehicle class does so with
        # ON DELETE RESTRICT, so the database refuses rather than cascading.
        # Nothing references one yet; the guard is here because the route that
        # would otherwise answer 500 is written now, not later.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle class is in use and cannot be removed.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
