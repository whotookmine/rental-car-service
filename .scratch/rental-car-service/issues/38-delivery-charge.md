# 38 — Distance-tiered delivery charge

**What to build:** What delivery costs, as a tier rather than a straight rate per
kilometre: the requirement says "distance-tiered", so a band of distances shares a price.

**Blocked by:** 37, 34

**Owner:** Garfield

**Status:** done

- [x] Delivery tiers are configuration — a set of distance bands, each with a charge —
      rather than numbers buried in code, and are stated in `docs/SPEC.md`
- [x] A quotation for a booking with delivery carries a delivery line at the tier its
      distance falls in
- [x] Tier boundaries are unambiguous and the boundary behaviour is stated: a distance
      exactly on a boundary must fall in exactly one tier, and which one is written down
- [x] A booking without delivery carries no delivery line at all
- [x] A distance beyond every tier is refused rather than silently charged at the top tier
- [x] The charge covers both delivery and collection, or charges each separately — decide
      which, state it, and make the itemisation say so
- [x] The figure on the quotation matches what the booking is created with

## Notes

- Tiers configured via `DELIVERY_TIERS` env var (JSON array). Default: 0–10km=200,
  11–20km=400, 21–50km=800 (THB). Stated in SPEC.md.
- Upper bound is **inclusive**: `distance <= tier.max_km`. First matching tier wins
  (tiers sorted ascending). Beyond last tier → 409.
- Charge covers delivery AND collection as one line ("Delivery and collection (up to N km)").
- `delivery_distance_km` and `delivery_address` added to `QuotationRequest` (same pair
  rule as booking: both or neither).
- No migration needed — all config + quotation logic.
- `DeliveryTier` model lives in `app/core/config.py` alongside the settings that use it.
- **Fixed after merge (2026-11-18):** the quotation priced delivery without checking the
  pickup branch's radius, so 30 km at a 20 km branch, or any distance at a branch with no
  delivery, was quoted although the booking refused it. That broke "the figure on the
  quotation matches what the booking is created with". The radius check moved from
  `app/bookings/router.py` into `ensure_delivery_within_radius` in `app/bookings/rules.py`,
  and both routes now call it. Found during the requirements-trace re-audit.
