# 31 — One-way enablement between branches

**What to build:** Which branch pairs a provider actually allows a one-way rental between.
The requirement is explicit that the combination is blocked unless the provider has enabled
one-way service between those two branches, so enablement is a decision a provider makes
per pair, not a global switch.

**Blocked by:** 30

**Owner:** Garfield

**Status:** done — verified against a running app and a real database

- [x] An admin enables one-way rental from one branch to another, for the same provider
- [x] An admin disables it again
- [x] Enablement is **directional**: enabling A to B does not enable B to A, because a
      provider may accept cars moving one way and not the other
- [x] Enabling a pair that has no recorded distance is refused, since the relocation fee
      could not then be computed
- [x] Any authenticated user can see which pairs are enabled for a provider
- [x] A registered user is refused 403 on every write
- [x] Disabling a pair leaves existing bookings that used it untouched

## Notes

- New package `app/one_way_routes/` with model, schemas, router.
- `OneWayRoute` uses `(from_branch_id, to_branch_id)` composite PK — **no canonical
  ordering**, unlike `BranchDistance`. Each direction is a separate row.
- Distance guard uses canonical ordering (min/max) to look up `BranchDistance`, since
  distances are symmetric and stored with the smaller id first.
- PUT is idempotent: re-enabling an existing pair returns the existing row.
- ON DELETE CASCADE on both FK columns, so removing a branch auto-removes its routes.
- "Disabling leaves bookings untouched" requires no code — ticket 32 will enforce the
  route at booking creation time; existing bookings carry no FK to `one_way_routes`.
