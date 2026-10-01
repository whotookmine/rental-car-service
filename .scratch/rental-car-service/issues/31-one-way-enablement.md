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


## Follow-up from Time — two gaps in the request schema

Found on 2026-10-02 while checking the pull, and fixed in a separate commit. Neither
touches this ticket's own behaviour, which was right: directional enablement, the distance
guard, the 403/401 split and the same-branch refusal all verified working afterwards.

**`OneWayRouteEnable` was missing `extra="forbid"`.** It was the only request schema in the
service without it — the sibling shapes in `branch_distances`, `branches` and `quotations`
all have it. I found it by accident, sending a body with a `relocation_fee` on the
assumption the fee lived on the route:

```
PUT /providers/{id}/one_way_routes  {"from_branch_id":1,"to_branch_id":2,"relocation_fee":"500.00"}
  before -> 200, the fee silently discarded
  after  -> 422 extra_forbidden
```

That is the failure the convention exists to prevent: the caller believes they set
something they did not. `docs/SPEC.md` already said extra fields are "refused, never
silently ignored".

**The branch ids were bounded below but not above**, so an over-large one reached
PostgreSQL and raised `NumericValueOutOfRange`:

```
PUT with from_branch_id 99999999999
  before -> 500 Internal Server Error
  after  -> 422
```

The DELETE path parameters on this same router already carried `le=2147483647`; only the
body shape lacked it.

Both rules are now in `CLAUDE.md` and `docs/SPEC.md`. I also swept every schema in the
service programmatically: these were the only two instances, and every other hit was a
response shape, which needs neither.
