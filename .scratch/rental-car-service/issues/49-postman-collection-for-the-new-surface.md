# 49 — Postman collection for the new surface

**What to build:** The collection extended to cover everything the second round added.
This supersedes ticket 22 rather than replacing it: that collection is the foundation and
this one grows it.

**Blocked by:** 47, 48

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] Every request from ticket 22 still passes unchanged, or its change is deliberate and
      explained
- [ ] New folders cover fleet, branches and one-way, money and quotations, delivery,
      maintenance, and the waitlist
- [ ] Dates are still computed in pre-request scripts and never hardcoded
- [ ] Identifiers created earlier in a run — a class, a branch, a claim — are captured into
      variables rather than pasted, so the collection runs end to end on a freshly seeded
      database
- [ ] The negative cases are present explicitly: a full class, a one-way pair that is not
      enabled, a delivery address beyond the radius, a booking over a blackout, joining a
      waitlist for a class that is not full, and claiming after the window has expired
- [ ] The FIFO chain is demonstrable: several users queue, one lets a claim expire, the
      next is offered it
- [ ] The quotation is shown matching what the booking is then created with
- [ ] The README documents the new commands, the new demo walkthrough, and every
      configurable value the new rules read
- [ ] The collection runs green end to end against a freshly seeded database
