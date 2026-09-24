# 26 — A full vehicle class refuses new bookings

**What to build:** The first real inventory rule. A class can only be booked as many times
over a given date range as it has vehicles. This is what makes "fully-booked" mean
something, and it is the precondition for the waitlist in ticket 43.

**Blocked by:** 25

**Owner:** Time

**Status:** ready-for-agent

- [ ] A booking is refused as a conflict when every vehicle in the class is already taken
      for any day of the requested rental period
- [ ] The refusal says the class is fully booked for those dates, not merely that something
      went wrong
- [ ] Overlap is counted per day: two bookings sharing even one day both consume capacity
      that day
- [ ] A class with three vehicles accepts three overlapping bookings and refuses the fourth
- [ ] Capacity frees the moment a booking is deleted, exactly as a user's own slot does
- [ ] The count is taken under a lock, so two simultaneous requests cannot both see the
      last vehicle and both take it — the same failure the three-active cap had, and the
      reason ADR 0001 chose PostgreSQL
- [ ] "Today" and all date comparisons go through the business-timezone helper
- [ ] The rule applies to admin edits as well as owner ones, measured against the class
