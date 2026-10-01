"""The fleet: the individual cars sitting in each vehicle class."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.auth.models import User
from app.db.session import get_db
from app.vehicle_classes.dependencies import get_vehicle_class_or_404
from app.vehicle_classes.models import VehicleClass
from app.vehicles.dependencies import get_vehicle_or_404
from app.vehicles.models import Vehicle
from app.vehicles.schemas import VehicleCreate, VehicleRead, VehicleUpdate

router = APIRouter(tags=["vehicles"])

# Every route here is admin-only. A plate identifies a particular car and is of
# no use to a renter, who books a kind of car; what a renter needs to know is how
# many there are, and that is reported as `vehicle_count` on the vehicle class
# itself rather than by listing the fleet.
#
# As elsewhere, `require_admin` is declared before the lookup dependencies on
# purpose: FastAPI resolves parameter dependencies in order, so a lookup first
# would answer 404 for something that does not exist before checking whether the
# caller is allowed to ask at all.

_DUPLICATE_PLATE = "A vehicle with that plate already exists."


def _duplicate_plate() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_DUPLICATE_PLATE)


def _refuse_duplicate_plate(
    db: Session, *, plate: str, excluding_id: int | None = None
) -> None:
    """Refuse a plate already on another car.

    The unique index is the guarantee; this lookup exists so the ordinary case
    gets a sentence a human can read rather than a database error.
    """
    stmt = select(Vehicle.id).where(func.lower(Vehicle.plate) == plate.lower())
    if excluding_id is not None:
        stmt = stmt.where(Vehicle.id != excluding_id)
    if db.execute(stmt).first() is not None:
        raise _duplicate_plate()


@router.get(
    "/vehicle_classes/{vehicle_class_id}/vehicles",
    response_model=list[VehicleRead],
    summary="List the cars in a vehicle class (admin only)",
    description=(
        "Ordered by plate, then id. Plates are fleet administration, not "
        "something a renter needs; any authenticated user can see how many cars "
        "a class has through `vehicle_count` on the class itself."
    ),
    responses={404: {"description": "Vehicle class not found."}},
)
def list_vehicles(
    _admin: User = Depends(require_admin),
    vehicle_class: VehicleClass = Depends(get_vehicle_class_or_404),
    db: Session = Depends(get_db),
) -> list[Vehicle]:
    return list(
        db.execute(
            select(Vehicle)
            .where(Vehicle.vehicle_class_id == vehicle_class.id)
            .order_by(Vehicle.plate, Vehicle.id)
        )
        .scalars()
        .all()
    )


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=VehicleRead,
    summary="Fetch a single vehicle (admin only)",
    responses={404: {"description": "Vehicle not found."}},
)
def get_vehicle(
    _admin: User = Depends(require_admin),
    vehicle: Vehicle = Depends(get_vehicle_or_404),
) -> Vehicle:
    return vehicle


@router.post(
    "/vehicle_classes/{vehicle_class_id}/vehicles",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a car to a vehicle class (admin only)",
    description=(
        "Raises that class's `vehicle_count`, which is the capacity ticket 26 "
        "enforces. Plates are unique across the whole system, compared without "
        "regard to case."
    ),
    responses={
        404: {"description": "Vehicle class not found."},
        409: {"description": _DUPLICATE_PLATE},
    },
)
def create_vehicle(
    payload: VehicleCreate,
    _admin: User = Depends(require_admin),
    vehicle_class: VehicleClass = Depends(get_vehicle_class_or_404),
    db: Session = Depends(get_db),
) -> Vehicle:
    _refuse_duplicate_plate(db, plate=payload.plate)

    vehicle = Vehicle(vehicle_class_id=vehicle_class.id, plate=payload.plate)
    db.add(vehicle)
    try:
        db.commit()
    except IntegrityError:
        # Two admins entering the same plate at once: the index caught what the
        # lookup above could not see.
        db.rollback()
        raise _duplicate_plate() from None
    db.refresh(vehicle)
    return vehicle


@router.patch(
    "/vehicles/{vehicle_id}",
    response_model=VehicleRead,
    summary="Edit a vehicle (admin only)",
    description=(
        "The plate can be corrected, and the car can be reclassified within the "
        "same provider's catalogue. Moving it to another provider's class is "
        "refused: that is a sale, not a reclassification."
    ),
    responses={
        404: {"description": "Vehicle not found."},
        409: {
            "description": (
                f"{_DUPLICATE_PLATE} Or the target class belongs to another provider."
            )
        },
        422: {"description": "The target vehicle class does not exist."},
    },
)
def update_vehicle(
    payload: VehicleUpdate,
    _admin: User = Depends(require_admin),
    vehicle: Vehicle = Depends(get_vehicle_or_404),
    db: Session = Depends(get_db),
) -> Vehicle:
    if payload.vehicle_class_id is not None:
        target = db.get(VehicleClass, payload.vehicle_class_id)
        if target is None:
            # 422 rather than 404: the missing thing is a value in the body, not
            # the resource the path addresses. The vehicle was found.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vehicle class not found.",
            )
        if target.provider_id != vehicle.vehicle_class.provider_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A vehicle cannot be moved to another provider's fleet.",
            )
        vehicle.vehicle_class_id = target.id

    if payload.plate is not None:
        _refuse_duplicate_plate(db, plate=payload.plate, excluding_id=vehicle.id)
        vehicle.plate = payload.plate

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _duplicate_plate() from None
    db.refresh(vehicle)
    return vehicle


@router.delete(
    "/vehicles/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a vehicle (admin only)",
    description=(
        "Lowers that class's `vehicle_count`. A car that anything else still "
        "points at — a maintenance blackout window — is refused with 409 rather "
        "than taking its references down with it."
    ),
    responses={
        404: {"description": "Vehicle not found."},
        409: {"description": "Vehicle is in use and cannot be removed."},
    },
)
def delete_vehicle(
    _admin: User = Depends(require_admin),
    vehicle: Vehicle = Depends(get_vehicle_or_404),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(vehicle)
    try:
        db.commit()
    except IntegrityError:
        # Every table that comes to reference a vehicle does so with
        # ON DELETE RESTRICT, so the database refuses rather than cascading.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehicle is in use and cannot be removed.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
