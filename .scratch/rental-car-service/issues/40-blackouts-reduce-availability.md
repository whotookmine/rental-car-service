# 40 — Blacked-out vehicles leave availability

**What to build:** A vehicle in the workshop is not a vehicle you can rent. Availability
must count only vehicles that are actually on the road for the whole requested range.

**Blocked by:** 39, 27

**Owner:** Time

**Status:** ready-for-agent

- [ ] Availability excludes any vehicle whose blackout window overlaps even one day of the
      requested range
- [ ] A class of three vehicles with one blacked out reports two available
- [ ] A class with every vehicle blacked out reports zero, not an error and not an omission
- [ ] A window that ends the day before the range starts does not reduce availability, and
      one that starts the day the range ends does — state the boundary explicitly
- [ ] Cancelling a window restores availability immediately
- [ ] Availability and booking still agree: whatever availability reports, booking behaves
      the same way
