"""Provider catalogue: browsing, creation, editing, and retirement."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User, UserRole
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider
from app.providers.schemas import ProviderCreate, ProviderRead, ProviderUpdate

router = APIRouter(prefix="/providers", tags=["providers"])

# Note for anyone editing the admin-only routes below: `require_admin` is
# declared before `get_provider_or_404` on purpose. FastAPI resolves parameter
# dependencies in the order they appear, so putting the lookup first would answer
# 404 for a provider that does not exist before checking whether the caller is
# allowed to be asking at all.


@router.get(
    "",
    response_model=list[ProviderRead],
    summary="List providers (authenticated)",
    description=(
        "Returns active providers. Admins may pass `include_retired=true` to "
        "include retired providers; registered users receive only active ones "
        "regardless of that parameter."
    ),
)
def list_providers(
    include_retired: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProviderRead]:
    stmt = select(Provider)
    if not include_retired or current_user.role != UserRole.admin:
        stmt = stmt.where(Provider.is_retired == False)  # noqa: E712
    providers = db.scalars(stmt).all()
    return [ProviderRead.model_validate(p) for p in providers]


@router.get(
    "/{provider_id}",
    response_model=ProviderRead,
    summary="Fetch a single provider by id (authenticated)",
    description="Returns the provider even if retired, so users can see who they booked with.",
    responses={404: {"description": "Provider not found."}},
)
def get_provider(
    provider: Provider = Depends(get_provider_or_404),
    _user: User = Depends(get_current_user),
) -> ProviderRead:
    return ProviderRead.model_validate(provider)


@router.post(
    "",
    response_model=ProviderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a provider (admin only)",
)
def create_provider(
    payload: ProviderCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ProviderRead:
    provider = Provider(
        name=payload.name,
        address=payload.address,
        telephone=payload.telephone,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return ProviderRead.model_validate(provider)


@router.patch(
    "/{provider_id}",
    response_model=ProviderRead,
    summary="Edit a provider's details (admin only)",
    responses={404: {"description": "Provider not found."}},
)
def update_provider(
    payload: ProviderUpdate,
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> ProviderRead:
    if payload.name is not None:
        provider.name = payload.name
    if payload.address is not None:
        provider.address = payload.address
    if payload.telephone is not None:
        provider.telephone = payload.telephone

    db.commit()
    db.refresh(provider)
    return ProviderRead.model_validate(provider)


@router.delete(
    "/{provider_id}",
    response_model=ProviderRead,
    summary="Retire a provider (admin only)",
    description=(
        "Marks the provider as retired. The record, existing bookings, and reviews "
        "are preserved. Retired providers are excluded from the catalogue list."
    ),
    responses={404: {"description": "Provider not found."}},
)
def retire_provider(
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> ProviderRead:
    provider.is_retired = True
    db.commit()
    db.refresh(provider)
    return ProviderRead.model_validate(provider)


@router.post(
    "/{provider_id}/reinstate",
    response_model=ProviderRead,
    summary="Reinstate a retired provider (admin only)",
    responses={404: {"description": "Provider not found."}},
)
def reinstate_provider(
    _admin: User = Depends(require_admin),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> ProviderRead:
    provider.is_retired = False
    db.commit()
    db.refresh(provider)
    return ProviderRead.model_validate(provider)
