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
