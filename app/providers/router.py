"""Provider catalogue: browsing, creation, editing, and retirement."""

from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy import Numeric, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User, UserRole
from app.bookings.models import Booking
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider
from app.providers.schemas import ProviderCreate, ProviderRead, ProviderUpdate
from app.reviews.models import Review

router = APIRouter(prefix="/providers", tags=["providers"])

# Note for anyone editing the admin-only routes below: `require_admin` is
# declared before `get_provider_or_404` on purpose. FastAPI resolves parameter
# dependencies in the order they appear, so putting the lookup first would answer
# 404 for a provider that does not exist before checking whether the caller is
# allowed to be asking at all.


def _ratings_subquery():
    """Subquery that aggregates review counts and averages per provider.

    Joining through bookings is necessary because reviews are attached to
    bookings, not directly to providers. LEFT JOIN so providers with no reviews
    still appear.
    """
    return (
        select(
            Booking.provider_id.label("provider_id"),
            func.round(func.avg(Review.rating).cast(Numeric), 1).label("average_rating"),
            func.count(Review.id).label("review_count"),
        )
        .outerjoin(Review, Review.booking_id == Booking.id)
        .group_by(Booking.provider_id)
        .subquery()
    )


def _build_read(provider: Provider, avg: Decimal | None, count: int) -> ProviderRead:
    return ProviderRead(
        id=provider.id,
        name=provider.name,
        address=provider.address,
        telephone=provider.telephone,
        is_retired=provider.is_retired,
        average_rating=float(avg) if avg is not None else None,
        review_count=count or 0,
    )


def _fetch_one(provider_id: int, db: Session) -> ProviderRead:
    ratings = _ratings_subquery()
    row = db.execute(
        select(Provider, ratings.c.average_rating, ratings.c.review_count)
        .outerjoin(ratings, ratings.c.provider_id == Provider.id)
        .where(Provider.id == provider_id)
    ).one()
    return _build_read(row[0], row[1], row[2])


@router.get(
    "",
    response_model=list[ProviderRead],
    summary="List providers (authenticated)",
    description=(
        "Returns active providers with their average rating and review count. "
        "Admins may pass `include_retired=true` to include retired providers; "
        "registered users receive only active ones regardless of that parameter. "
        "Ordered by name, then by id for ties."
    ),
)
def list_providers(
    include_retired: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProviderRead]:
    ratings = _ratings_subquery()
    stmt = (
        select(Provider, ratings.c.average_rating, ratings.c.review_count)
        .outerjoin(ratings, ratings.c.provider_id == Provider.id)
        .order_by(Provider.name, Provider.id)
    )
    if not include_retired or current_user.role != UserRole.admin:
        stmt = stmt.where(Provider.is_retired == False)  # noqa: E712

    rows = db.execute(stmt).all()
    return [_build_read(row[0], row[1], row[2]) for row in rows]


@router.get(
    "/{provider_id}",
    response_model=ProviderRead,
    summary="Fetch a single provider by id (authenticated)",
    description=(
        "Returns the provider with its average rating and review count, "
        "even if retired, so users can see who they booked with."
    ),
    responses={404: {"description": "Provider not found."}},
)
def get_provider(
    provider: Provider = Depends(get_provider_or_404),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProviderRead:
    return _fetch_one(provider.id, db)


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
    return _fetch_one(provider.id, db)


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
    return _fetch_one(provider.id, db)


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
    return _fetch_one(provider.id, db)


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
    return _fetch_one(provider.id, db)
