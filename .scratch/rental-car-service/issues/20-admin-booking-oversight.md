# 20 — Admin booking oversight

**What to build:** An admin can see and act on every booking in the system, to support
customers and correct mistakes. Scope widens by role on the same routes rather than
through a separate admin namespace, so the ownership rule lives in one place and cannot
drift between two copies. An admin has wider reach, not weaker rules: their edits are
validated exactly as an owner's are.

**Blocked by:** 12, 13

**Owner:** Time

**Status:** ready-for-agent

- [ ] Listing bookings returns every booking in the system when the caller is an admin,
      and only the caller's own when they are a registered user — the same route for both
- [ ] An admin fetches any single booking by identifier
- [ ] An admin changes the dates on any booking
- [ ] An admin deletes any booking
- [ ] Admin edits are validated by exactly the same rules an owner faces, including the
      thirty-day maximum and the three-active-booking cap measured against the booking's
      owner
- [ ] A consequence to accept rather than work around: an admin cannot extend an ended
      booking for a user who already holds three active ones, even to correct a genuine
      error
- [ ] An admin cannot change which provider a booking is with
- [ ] Admins do not hold bookings of their own; an admin attempting to create one is
      refused
