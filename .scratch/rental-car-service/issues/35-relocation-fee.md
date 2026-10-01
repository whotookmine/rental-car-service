# 35 — Relocation fee for one-way rentals

**What to build:** The cost of getting the car back. A one-way rental adds a fee computed
from the distance between the two branches, and it appears on the quotation as its own
line.

**Blocked by:** 34, 32

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] A quotation for a one-way rental carries a relocation line computed from the recorded
      inter-branch distance
- [ ] A same-branch rental carries no relocation line at all, rather than a line of zero
- [ ] The rate per kilometre is configurable rather than hardcoded, and is stated in
      `docs/SPEC.md`
- [ ] The fee appears in the total as well as in the itemisation
- [ ] Quoting a one-way combination the provider has not enabled is refused, matching what
      booking does, so a user is never quoted for something they cannot book
- [ ] A one-way pair that is enabled but has no recorded distance cannot occur, because
      ticket 31 refuses to enable it — verify that rather than assume it
- [ ] Creating the booking produces the same figure the quotation gave for the same inputs

## Note from Time — 2026-10-02: this is the last clause of requirement 5

Requirement 5 as given has three parts: support one-way rentals, **compute a relocation fee
from the inter-branch distance**, and block the combination when the provider has not
enabled it. Tickets 31 and 32 landed the first and third. This ticket is the second, and
until it lands requirement 5 reads as half-done.

Verified today against the running app — the one-way quotation carries no fee line:

```
POST /providers/1/quotations
  {"vehicle_class_id":1,"pickup_branch_id":1,"dropoff_branch_id":2, ...}
-> 200
   lines: [ "Economy × 2 days @ THB 1200.00/day"  2400.00 ]
   total:   2400.00
```

Both halves it needs already exist: the distances from ticket 30 and the quotation from
ticket 34. Recorded in `docs/REQUIREMENTS-TRACE.md`, which should move this row from
"not built" to verified in the same commit as the work.
