"""One-way enablement: which branch pairs a provider allows one-way rentals between."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.branch_distances.models import BranchDistance
from app.branches.models import Branch
from app.db.session import get_db
from app.one_way_routes.models import OneWayRoute
from app.one_way_routes.schemas import OneWayRouteEnable, OneWayRouteRead
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider

router = APIRouter(tags=["one-way routes"])

BranchIdPath = Annotated[int, Path(ge=1, le=2147483647)]


def _resolve_branch_for_provider(
    db: Session,
    provider: Provider,
    branch_id: int,
    field_name: str,
) -> Branch:
    branch = db.get(Branch, branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Branch {branch_id} not found.",
        )
    if branch.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Branch '{branch.name}' does not belong to provider '{provider.name}'.",
        )
    return branch


def _require_distance_exists(db: Session, from_id: int, to_id: int) -> None:
    """Refuse enablement when no distance is recorded for this pair."""
    lo, hi = min(from_id, to_id), max(from_id, to_id)
    row = db.get(BranchDistance, (lo, hi))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No distance is recorded between these two branches. "
                "Record the distance before enabling one-way service."
            ),
        )


@router.put(
    "/providers/{provider_id}/one_way_routes",
    response_model=OneWayRouteRead,
    summary="Enable one-way rental between two branches (admin only)",
    description=(
        "Enables one-way rental from one branch to another for this provider. "
        "Directional: enabling A→B does not enable B→A. "
        "A recorded distance between the branches must exist before enablement. "
        "Submitting an already-enabled pair is idempotent."
    ),
    responses={
        404: {"description": "Provider not found."},
        409: {"description": "A branch belongs to a different provider, or no distance recorded."},
        422: {"description": "A branch does not exist, or branches are the same."},
    },
)
def enable_one_way_route(
    payload: OneWayRouteEnable,
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> OneWayRouteRead:
    _resolve_branch_for_provider(db, provider, payload.from_branch_id, "from_branch_id")
    _resolve_branch_for_provider(db, provider, payload.to_branch_id, "to_branch_id")
    _require_distance_exists(db, payload.from_branch_id, payload.to_branch_id)

    row = db.get(OneWayRoute, (payload.from_branch_id, payload.to_branch_id))
    if row is None:
        row = OneWayRoute(
            from_branch_id=payload.from_branch_id,
            to_branch_id=payload.to_branch_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return OneWayRouteRead.model_validate(row)


@router.get(
    "/providers/{provider_id}/one_way_routes",
    response_model=list[OneWayRouteRead],
    summary="List one-way routes for a provider (authenticated)",
    description="Returns all enabled one-way branch pairs for this provider, ordered by from_branch_id then to_branch_id.",
    responses={
        404: {"description": "Provider not found."},
    },
)
def list_one_way_routes(
    _user: User = Depends(get_current_user),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> list[OneWayRouteRead]:
    rows = (
        db.query(OneWayRoute)
        .join(OneWayRoute.from_branch)
        .filter(Branch.provider_id == provider.id)
        .order_by(OneWayRoute.from_branch_id, OneWayRoute.to_branch_id)
        .all()
    )
    return [OneWayRouteRead.model_validate(r) for r in rows]


@router.delete(
    "/providers/{provider_id}/one_way_routes/{from_branch_id}/{to_branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disable one-way rental between two branches (admin only)",
    description=(
        "Removes the one-way enablement from one branch to another. "
        "Directional: disabling A→B does not affect B→A. "
        "Existing bookings that used this route are left untouched."
    ),
    responses={
        404: {"description": "Provider not found, or route not enabled."},
        409: {"description": "A branch belongs to a different provider."},
        422: {"description": "A branch does not exist, or branches are the same."},
    },
)
def disable_one_way_route(
    from_branch_id: BranchIdPath,
    to_branch_id: BranchIdPath,
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> Response:
    if from_branch_id == to_branch_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="from_branch_id and to_branch_id must be different.",
        )
    _resolve_branch_for_provider(db, provider, from_branch_id, "from_branch_id")
    _resolve_branch_for_provider(db, provider, to_branch_id, "to_branch_id")

    row = db.get(OneWayRoute, (from_branch_id, to_branch_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One-way route not enabled between these branches.",
        )
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
