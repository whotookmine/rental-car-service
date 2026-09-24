# 38 — Distance-tiered delivery charge

**What to build:** What delivery costs, as a tier rather than a straight rate per
kilometre: the requirement says "distance-tiered", so a band of distances shares a price.

**Blocked by:** 37, 34

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] Delivery tiers are configuration — a set of distance bands, each with a charge —
      rather than numbers buried in code, and are stated in `docs/SPEC.md`
- [ ] A quotation for a booking with delivery carries a delivery line at the tier its
      distance falls in
- [ ] Tier boundaries are unambiguous and the boundary behaviour is stated: a distance
      exactly on a boundary must fall in exactly one tier, and which one is written down
- [ ] A booking without delivery carries no delivery line at all
- [ ] A distance beyond every tier is refused rather than silently charged at the top tier
- [ ] The charge covers both delivery and collection, or charges each separately — decide
      which, state it, and make the itemisation say so
- [ ] The figure on the quotation matches what the booking is created with
