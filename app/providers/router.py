"""Provider catalogue: browsing, creation, editing, and retirement."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Numeric, func, select, text
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User, UserRole
from app.bookings.models import Booking
from app.bookings.schemas import validate_rental_period
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider
from app.providers.schemas import AvailabilityRow, ProviderCreate, ProviderRead, ProviderUpdate
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


def _build_read(provider: Provider, avg: Decimal | None, count: int | None) -> ProviderRead:
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


_AVAILABILITY_QUERY = text(
    """
    WITH days AS (
        SELECT generate_series(
            CAST(:start_date AS date),
            CAST(:end_date AS date),
            CAST('1 day' AS interval)
        ) AS day
    ),
    class_capacity AS (
        SELECT vc.id, vc.name, COUNT(v.id) AS cap
        FROM vehicle_classes vc
        LEFT JOIN vehicles v ON v.vehicle_class_id = vc.id
        WHERE vc.provider_id = :provider_id
        GROUP BY vc.id, vc.name
    ),
    daily_bookings AS (
        SELECT cc.id AS vehicle_class_id, d.day, COUNT(b.id) AS taken
        FROM days d
        CROSS JOIN class_capacity cc
        LEFT JOIN bookings b ON b.vehicle_class_id = cc.id
            AND b.start_date <= d.day AND b.end_date >= d.day
        GROUP BY cc.id, d.day
    ),
    peak_bookings AS (
        SELECT vehicle_class_id, MAX(taken) AS peak
        FROM daily_bookings
        GROUP BY vehicle_class_id
    )
    SELECT
        cc.id          AS vehicle_class_id,
        cc.name        AS name,
        GREATEST(0, CAST(cc.cap AS integer) - CAST(COALESCE(pb.peak, 0) AS integer))
                       AS free_count
    FROM class_capacity cc
    LEFT JOIN peak_bookings pb ON pb.vehicle_class_id = cc.id
    ORDER BY cc.id
    """
)


@router.get(
    "/{provider_id}/availability",
    response_model=list[AvailabilityRow],
    summary="Check vehicle class availability (authenticated)",
    description=(
        "Returns each vehicle class for the provider with the number of cars free "
        "for the whole requested rental period. A class reporting zero is full; it "
        "is never omitted. Retired providers are excluded. The same date rules as "
        "booking apply: end on or after start, at most thirty days."
    ),
    responses={
        404: {"description": "Provider not found."},
        422: {"description": "Invalid date range."},
    },
)
def get_availability(
    start_date: date = Query(...),
    end_date: date = Query(...),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> list[AvailabilityRow]:
    try:
        validate_rental_period(start_date, end_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Retired providers are invisible here, matching the active catalogue list.
    if provider.is_retired:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider not found.",
        )

    rows = db.execute(
        _AVAILABILITY_QUERY,
        {
            "provider_id": provider.id,
            "start_date": start_date,
            "end_date": end_date,
        },
    ).fetchall()

    return [
        AvailabilityRow(
            vehicle_class_id=row.vehicle_class_id,
            name=row.name,
            free_count=row.free_count,
        )
        for row in rows
    ]


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
