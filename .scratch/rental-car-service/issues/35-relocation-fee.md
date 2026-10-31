# 35 — Relocation fee for one-way rentals

**What to build:** The cost of getting the car back. A one-way rental adds a fee computed
from the distance between the two branches, and it appears on the quotation as its own
line.

**Blocked by:** 34, 32

**Owner:** Garfield

**Status:** done

- [x] A quotation for a one-way rental carries a relocation line computed from the recorded
      inter-branch distance
- [x] A same-branch rental carries no relocation line at all, rather than a line of zero
- [x] The rate per kilometre is configurable rather than hardcoded, and is stated in
      `docs/SPEC.md`
- [x] The fee appears in the total as well as in the itemisation
- [x] Quoting a one-way combination the provider has not enabled is refused, matching what
      booking does, so a user is never quoted for something they cannot book
- [x] A one-way pair that is enabled but has no recorded distance cannot occur, because
      ticket 31 refuses to enable it — verify that rather than assume it
- [x] Creating the booking produces the same figure the quotation gave for the same inputs

## Notes

- No migration needed — the relocation fee is computed at quote time from existing
  `branch_distances` rows.
- Rate is `RELOCATION_RATE_PER_KM` in settings, default **THB 50.00/km**, stated in SPEC.md.
- Distance looked up via canonical ordering (smaller branch id first), matching the
  `branch_distances` storage convention from ticket 30.
- `round_amount()` applied to the relocation line amount, same as the rental line, so
  no floating-point accumulation before the final total round.
- The "enabled but no distance" path is guarded defensively in code but is an invariant
  from ticket 31: enabling a route without a recorded distance is already refused (409).
  Verified by testing B2→B1 (not enabled) returns 409.
