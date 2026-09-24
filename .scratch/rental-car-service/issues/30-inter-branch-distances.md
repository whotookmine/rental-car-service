# 30 — Inter-branch distances

**What to build:** How far apart two branches are, recorded by an admin rather than
computed from coordinates. Both the relocation fee and the delivery charge are distance
tiers, so distance has to be a number the system knows.

Deliberately not geocoding: an external mapping API means keys, quotas, network failures
and cost, for a number an admin can type once. See the ADR in ticket 48.

**Blocked by:** 28

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] An admin records the distance in kilometres between two branches of the same provider
- [ ] An admin edits and removes a distance
- [ ] Distance is symmetric: recording A to B also answers B to A, without a second row
- [ ] A distance between branches of different providers is refused
- [ ] A distance from a branch to itself is refused, or is always zero and not stored
- [ ] Negative or non-numeric distances are refused as unprocessable
- [ ] Recording the same pair twice updates rather than duplicating
- [ ] Any authenticated user can read a distance; only an admin can write one
- [ ] A missing distance is reported as absent rather than assumed to be zero, since a
      zero relocation fee and an unknown one are different things
