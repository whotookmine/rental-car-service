# 28 — Branches under a provider

**What to build:** A provider stops being a single address and becomes a business with
places you collect a car from. One-way rentals and delivery radii are both defined between
or around branches, so neither requirement is expressible until branches exist.

**Blocked by:** None — can start immediately

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] An admin creates a branch under a provider, with a name, address and telephone
- [ ] An admin edits and removes a branch
- [ ] Any authenticated user lists a provider's branches and fetches one by identifier
- [ ] A registered user is refused 403 on every write
- [ ] A provider always has at least one branch; removing the last one is refused
- [ ] Removing a branch referenced by a booking is refused rather than cascading
- [ ] The provider's existing single address becomes its first branch in the migration,
      so no provider is left without one and no address is lost
- [ ] The migration states what it did with the old column, and whether the provider keeps
      an address of its own or now reads it from the branch
