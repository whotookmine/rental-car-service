# 31 — One-way enablement between branches

**What to build:** Which branch pairs a provider actually allows a one-way rental between.
The requirement is explicit that the combination is blocked unless the provider has enabled
one-way service between those two branches, so enablement is a decision a provider makes
per pair, not a global switch.

**Blocked by:** 30

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] An admin enables one-way rental from one branch to another, for the same provider
- [ ] An admin disables it again
- [ ] Enablement is **directional**: enabling A to B does not enable B to A, because a
      provider may accept cars moving one way and not the other
- [ ] Enabling a pair that has no recorded distance is refused, since the relocation fee
      could not then be computed
- [ ] Any authenticated user can see which pairs are enabled for a provider
- [ ] A registered user is refused 403 on every write
- [ ] Disabling a pair leaves existing bookings that used it untouched
