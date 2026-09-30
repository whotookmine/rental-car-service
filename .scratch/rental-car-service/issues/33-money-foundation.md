# 33 — Money foundation

**What to build:** The system's first notion of price. Until now nothing cost anything;
the second round of requirements computes a relocation fee and a delivery charge and adds
them to a quotation, so money has to exist before either can.

This is the largest single addition of the round and the easiest to get subtly wrong, so
it lands on its own rather than inside a feature.

**Blocked by:** 25

**Owner:** Garfield

**Status:** done — verified against a running app and a real database

- [x] Amounts are stored as exact decimals, never as floating point: money that rounds
      differently on different machines is a defect that surfaces only in totals
- [x] A single currency, named in configuration rather than hardcoded, since the brief
      describes one market
- [x] A vehicle class carries a daily rate, set and edited by an admin
- [x] A negative or non-numeric rate is refused as unprocessable
- [x] A rate of zero is allowed and means free, which is different from having no rate
- [x] A class with no rate set is reported as unpriced rather than as costing nothing
- [x] Rounding is defined once, stated in `docs/SPEC.md`, and applied in one place
- [x] Amounts appear in responses in a single consistent shape, decided here and used by
      every later ticket

## Notes

- `app/core/money.py` owns the `Money` schema and `round_amount()`. Single home for
  rounding; later tickets import both from here.
- `Money.amount` serialises as a string in JSON (`@field_serializer`). This prevents
  float conversion across the JSON boundary.
- `CURRENCY` added to `Settings` (default `THB`), with `.env.example` updated.
- `VehicleClass.daily_rate` is `NUMERIC(12, 2)` nullable. Null = unpriced; zero = free.
- `VehicleClassSummary` uses `@field_validator(mode="before")` on `daily_rate` to
  convert `Decimal` → `Money` when read from ORM. This keeps the booking response
  consistent without needing a manual build step.
- `VehicleClassUpdate` uses `model_fields_set` to distinguish `daily_rate` omitted
  (no change) from `daily_rate: null` (remove price).
- `_build_read` in the vehicle class router constructs `Money` explicitly for
  `VehicleClassRead`, which is built from column values rather than ORM attributes.
