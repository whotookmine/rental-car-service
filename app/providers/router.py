"""Provider catalogue: creation and editing (admin only)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_admin
from app.auth.models import User
from app.db.session import get_db
from app.providers.models import Provider
from app.providers.schemas import ProviderCreate, ProviderRead, ProviderUpdate

router = APIRouter(prefix="/providers", tags=["providers"])


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
    provider_id: int,
    payload: ProviderUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ProviderRead:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found.",
        )

    if payload.name is not None:
        provider.name = payload.name
    if payload.address is not None:
        provider.address = payload.address
    if payload.telephone is not None:
        provider.telephone = payload.telephone

    db.commit()
    db.refresh(provider)
    return ProviderRead.model_validate(provider)
