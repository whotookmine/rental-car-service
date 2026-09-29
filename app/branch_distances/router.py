"""Inter-branch distances: how far apart two of a provider's branches are."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.branch_distances.models import BranchDistance
from app.branch_distances.schemas import BranchDistanceRead, BranchDistanceSet
from app.branches.models import Branch
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider

router = APIRouter(tags=["branch distances"])

# Annotated type so each parameter gets its own FieldInfo instance — reusing
# a single Path() object for two params in the same function causes FastAPI to
# conflate them and read both from the same path segment.
BranchIdPath = Annotated[int, Path(ge=1, le=2147483647)]


def _canonical(a: int, b: int) -> tuple[int, int]:
    """Return (smaller, larger) — the canonical pair used for storage."""
    return (min(a, b), max(a, b))


def _resolve_branches_for_provider(
    db: Session,
    provider: Provider,
    branch_a_id: int,
    branch_b_id: int,
) -> tuple[Branch, Branch]:
    """Fetch both branches and verify they belong to the provider.

    Two separate refusals, matching the pattern for vehicle classes and branches
    in bookings:
    - A branch that does not exist is a bad body value — 422.
    - A branch that belongs to a different provider is a state conflict — 409.
    """
    a = db.get(Branch, branch_a_id)
    if a is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Branch {branch_a_id} not found.",
        )
    if a.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Branch '{a.name}' does not belong to provider '{provider.name}'."
            ),
        )
    b = db.get(Branch, branch_b_id)
    if b is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Branch {branch_b_id} not found.",
        )
    if b.provider_id != provider.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Branch '{b.name}' does not belong to provider '{provider.name}'."
            ),
        )
    return a, b


def _get_distance_or_404(
    db: Session, from_id: int, to_id: int
) -> BranchDistance:
    row = db.get(BranchDistance, (from_id, to_id))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No distance recorded between these two branches.",
        )
    return row


@router.put(
    "/providers/{provider_id}/branch_distances",
    response_model=BranchDistanceRead,
    summary="Record or update distance between two branches (admin only)",
    description=(
        "Records the distance in kilometres between two of the provider's branches. "
        "Symmetric: A to B is the same as B to A — one row, no second entry needed. "
        "Submitting the same pair again updates the distance rather than duplicating. "
        "Both branches must belong to this provider."
    ),
    responses={
        404: {"description": "Provider not found."},
        409: {"description": "A branch belongs to a different provider."},
        422: {"description": "A branch does not exist, or the branches are the same, or distance is not positive."},
    },
)
def upsert_distance(
    payload: BranchDistanceSet,
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> BranchDistanceRead:
    _resolve_branches_for_provider(
        db, provider, payload.from_branch_id, payload.to_branch_id
    )

    from_id, to_id = _canonical(payload.from_branch_id, payload.to_branch_id)

    row = db.get(BranchDistance, (from_id, to_id))
    if row is None:
        row = BranchDistance(
            from_branch_id=from_id,
            to_branch_id=to_id,
            distance_km=payload.distance_km,
        )
        db.add(row)
    else:
        row.distance_km = payload.distance_km

    db.commit()
    db.refresh(row)
    return BranchDistanceRead.model_validate(row)


@router.get(
    "/providers/{provider_id}/branch_distances/{branch_a_id}/{branch_b_id}",
    response_model=BranchDistanceRead,
    summary="Fetch the distance between two branches (authenticated)",
    description=(
        "Returns the recorded distance between two branches. Symmetric: querying "
        "A to B returns the same result as B to A. Answers 404 if no distance has "
        "been recorded for this pair — an absent distance is not assumed to be zero."
    ),
    responses={
        404: {"description": "Provider not found, or no distance recorded for this pair."},
        409: {"description": "A branch belongs to a different provider."},
        422: {"description": "A branch does not exist, or the branches are the same."},
    },
)
def get_distance(
    branch_a_id: BranchIdPath,
    branch_b_id: BranchIdPath,
    _user: User = Depends(get_current_user),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> BranchDistanceRead:
    if branch_a_id == branch_b_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="branch_a_id and branch_b_id must be different.",
        )
    _resolve_branches_for_provider(db, provider, branch_a_id, branch_b_id)

    from_id, to_id = _canonical(branch_a_id, branch_b_id)
    return BranchDistanceRead.model_validate(_get_distance_or_404(db, from_id, to_id))


@router.delete(
    "/providers/{provider_id}/branch_distances/{branch_a_id}/{branch_b_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove the distance between two branches (admin only)",
    responses={
        404: {"description": "Provider not found, or no distance recorded for this pair."},
        409: {"description": "A branch belongs to a different provider."},
        422: {"description": "A branch does not exist, or the branches are the same."},
    },
)
def delete_distance(
    branch_a_id: BranchIdPath,
    branch_b_id: BranchIdPath,
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> Response:
    if branch_a_id == branch_b_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="branch_a_id and branch_b_id must be different.",
        )
    _resolve_branches_for_provider(db, provider, branch_a_id, branch_b_id)

    from_id, to_id = _canonical(branch_a_id, branch_b_id)
    row = _get_distance_or_404(db, from_id, to_id)
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
