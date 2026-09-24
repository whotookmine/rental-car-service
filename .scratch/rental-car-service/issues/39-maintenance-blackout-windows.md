# 39 — Maintenance blackout windows

**What to build:** Periods when a particular vehicle is off the road for servicing. The
requirement schedules these per vehicle, which is why ticket 24 models individual units
rather than only classes.

**Blocked by:** 24

**Owner:** Time

**Status:** ready-for-agent

- [ ] An admin schedules a blackout window on one vehicle, with a start and end date
- [ ] An admin edits and cancels a window
- [ ] The same date shape rules apply as everywhere else: end on or after start, counted
      inclusively
- [ ] A window may be scheduled in the past, so that history can be recorded and corrected
- [ ] Two overlapping windows on the same vehicle are refused, or merged — decide which,
      state it, and be consistent
- [ ] Any authenticated user can see that a vehicle is unavailable; only an admin can
      schedule
- [ ] A registered user is refused 403 on every write
- [ ] All date comparisons go through the business-timezone helper
- [ ] The window's foreign key to its vehicle is `ON DELETE RESTRICT`, matching tickets 23
      and 24: removing a vehicle that has a blackout window must answer 409, never cascade
