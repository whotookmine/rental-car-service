"""Money types and rounding for the service.

All monetary amounts are exact decimals. Rounding is half-up to two decimal
places, defined once here and applied in one place rather than at every call
site. Floating-point is never used for money: a float that rounds differently
on different machines is a defect that surfaces only in totals.

The response shape is a `Money` object with an `amount` string and a
`currency` code. String serialisation of the amount preserves the exact
decimal value across the JSON boundary; a JSON number would invite a
float round-trip.
"""

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, field_serializer

TWO_PLACES = Decimal("0.01")


def round_amount(value: Decimal) -> Decimal:
    """Round to two decimal places, half-up."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class Money(BaseModel):
    """A monetary amount with its currency code.

    `amount` serialises as a string in JSON so the exact decimal value
    survives the round-trip without float conversion.
    """

    amount: Decimal
    currency: str

    @field_serializer("amount")
    def _serialize_amount(self, value: Decimal) -> str:
        return str(value)
