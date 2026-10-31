"""Branch catalogue: pickup locations under a provider."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.branches.dependencies import get_branch_or_404
from app.branches.models import Branch
from app.branches.schemas import BranchCreate, BranchRead, BranchUpdate, DeliveryRadiusSet
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider

router = APIRouter(tags=["branches"])

# As in the provider and vehicle class routers, `require_admin` is declared
# before lookup dependencies on purpose: FastAPI resolves parameter dependencies
# in the order they appear, so putting a lookup first would answer 404 before
# checking whether the caller is allowed to ask at all.


@router.get(
    "/providers/{provider_id}/branches",
    response_model=list[BranchRead],
    summary="List a provider's branches (authenticated)",
    description=(
        "Returns all pickup locations for this provider, ordered by name then id. "
        "Branches under a retired provider are still listed, so a user can see "
        "where they collected their car."
    ),
    responses={404: {"description": "Provider not found."}},
)
def list_branches(
    provider: Provider = Depends(get_provider_or_404),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BranchRead]:
    branches = db.scalars(
        select(Branch)
        .where(Branch.provider_id == provider.id)
        .order_by(Branch.name, Branch.id)
    ).all()
    return [BranchRead.model_validate(b) for b in branches]


@router.get(
    "/branches/{branch_id}",
    response_model=BranchRead,
    summary="Fetch a single branch (authenticated)",
    responses={404: {"description": "Branch not found."}},
)
def get_branch(
    branch: Branch = Depends(get_branch_or_404),
) -> BranchRead:
    return BranchRead.model_validate(branch)


@router.post(
    "/providers/{provider_id}/branches",
    response_model=BranchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a branch to a provider (admin only)",
    responses={404: {"description": "Provider not found."}},
)
def create_branch(
    payload: BranchCreate,
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> BranchRead:
    branch = Branch(
        provider_id=provider.id,
        name=payload.name,
        address=payload.address,
        telephone=payload.telephone,
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return BranchRead.model_validate(branch)


@router.patch(
    "/branches/{branch_id}",
    response_model=BranchRead,
    summary="Edit a branch (admin only)",
    description="Only name, address, and telephone are editable.",
    responses={404: {"description": "Branch not found."}},
)
def update_branch(
    payload: BranchUpdate,
    _admin: User = Depends(require_admin),
    branch: Branch = Depends(get_branch_or_404),
    db: Session = Depends(get_db),
) -> BranchRead:
    if payload.name is not None:
        branch.name = payload.name
    if payload.address is not None:
        branch.address = payload.address
    if payload.telephone is not None:
        branch.telephone = payload.telephone

    db.commit()
    db.refresh(branch)
    return BranchRead.model_validate(branch)


@router.put(
    "/branches/{branch_id}/delivery-radius",
    response_model=BranchRead,
    summary="Set delivery radius on a branch (admin only)",
    description="Sets how far (in km) this branch will deliver. A radius of zero is valid.",
    responses={404: {"description": "Branch not found."}},
)
def set_delivery_radius(
    payload: DeliveryRadiusSet,
    _admin: User = Depends(require_admin),
    branch: Branch = Depends(get_branch_or_404),
    db: Session = Depends(get_db),
) -> BranchRead:
    branch.delivery_radius_km = payload.kilometres
    db.commit()
    db.refresh(branch)
    return BranchRead.model_validate(branch)


@router.delete(
    "/branches/{branch_id}/delivery-radius",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear delivery radius on a branch (admin only)",
    description="Withdraws delivery from this branch. Existing bookings that used delivery are not affected.",
    responses={404: {"description": "Branch not found."}},
)
def clear_delivery_radius(
    _admin: User = Depends(require_admin),
    branch: Branch = Depends(get_branch_or_404),
    db: Session = Depends(get_db),
) -> Response:
    branch.delivery_radius_km = None
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/branches/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a branch (admin only)",
    description=(
        "Removes the branch outright. Refused if it is the provider's last branch "
        "— every provider must always have at least one — or if a booking names it "
        "as the pickup location."
    ),
    responses={
        404: {"description": "Branch not found."},
        409: {
            "description": (
                "The branch is the provider's last and cannot be removed, or it "
                "is named by a booking."
            )
        },
    },
)
def delete_branch(
    _admin: User = Depends(require_admin),
    branch: Branch = Depends(get_branch_or_404),
    db: Session = Depends(get_db),
) -> Response:
    branch_count = (
        db.scalar(
            select(func.count())
            .select_from(Branch)
            .where(Branch.provider_id == branch.provider_id)
        )
        or 0
    )
    if branch_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A provider must have at least one branch. Add another branch "
                "before removing this one."
            ),
        )

    db.delete(branch)
    try:
        db.commit()
    except IntegrityError:
        # A booking names this branch as its pickup location (ticket 29 adds
        # that FK with ON DELETE RESTRICT). The guard is here now so the route
        # that would otherwise answer 500 is already correct when that column
        # lands.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Branch is named by a booking and cannot be removed.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
