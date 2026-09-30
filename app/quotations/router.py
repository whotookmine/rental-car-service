"""Quotations: what a proposed booking would cost, itemised, before committing."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.bookings.rules import (
    ensure_one_way_route_enabled,
    resolve_branch_for_provider,
    resolve_vehicle_class_for_provider,
)
from app.bookings.schemas import rental_period_days
from app.core.config import get_settings
from app.core.money import Money, round_amount
from app.db.session import get_db
from app.providers.dependencies import get_provider_or_404
from app.providers.models import Provider
from app.quotations.schemas import QuotationLine, QuotationRead, QuotationRequest

router = APIRouter(tags=["quotations"])


@router.post(
    "/providers/{provider_id}/quotations",
    response_model=QuotationRead,
    summary="Get an itemised cost estimate for a proposed booking (authenticated)",
    description=(
        "Returns a line-by-line cost breakdown for a proposed booking without "
        "reserving anything. The same date and branch validation as booking "
        "creation applies. A class with no daily rate set cannot be priced."
    ),
    responses={
        404: {"description": "Provider not found."},
        409: {
            "description": (
                "The vehicle class or a branch belongs to a different provider, "
                "a one-way combination has not been enabled, or the vehicle class "
                "has no daily rate set."
            )
        },
        422: {"description": "The vehicle class or a branch does not exist, or dates are invalid."},
    },
)
def create_quotation(
    payload: QuotationRequest,
    _user: User = Depends(get_current_user),
    provider: Provider = Depends(get_provider_or_404),
    db: Session = Depends(get_db),
) -> QuotationRead:
    vehicle_class = resolve_vehicle_class_for_provider(
        db, provider, payload.vehicle_class_id
    )
    pickup_branch = resolve_branch_for_provider(db, provider, payload.pickup_branch_id)

    if payload.dropoff_branch_id is not None:
        dropoff_branch = resolve_branch_for_provider(
            db, provider, payload.dropoff_branch_id
        )
        if dropoff_branch.id != pickup_branch.id:
            ensure_one_way_route_enabled(db, pickup_branch, dropoff_branch)

    if vehicle_class.daily_rate is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Vehicle class '{vehicle_class.name}' has no daily rate set "
                "and cannot be priced."
            ),
        )

    currency = get_settings().currency
    days = rental_period_days(payload.start_date, payload.end_date)
    rental_amount = vehicle_class.daily_rate * Decimal(days)

    lines = [
        QuotationLine(
            description=(
                f"{vehicle_class.name} \u00d7 {days} "
                f"{'day' if days == 1 else 'days'} "
                f"@ {currency} {vehicle_class.daily_rate}/day"
            ),
            amount=Money(amount=rental_amount, currency=currency),
        )
    ]

    total = round_amount(sum(line.amount.amount for line in lines))

    return QuotationRead(
        lines=lines,
        total=Money(amount=total, currency=currency),
    )
