# 43 — Joining the waitlist

**What to build:** When a class is full for the dates someone wants, they can queue for it
instead of simply being refused. The queue is per provider, class and date range, and its
order is the order people joined — that ordering is what ticket 44 depends on.

**Blocked by:** 26

**Owner:** Time

**Status:** ready-for-agent

- [ ] A registered user joins the waitlist for a provider, vehicle class and date range
- [ ] Joining is refused when the class is **not** full for those dates, since they should
      simply book it
- [ ] A user may not join the same queue twice; the second attempt is a conflict
- [ ] A user sees their own waitlist entries and where they stand in the queue
- [ ] A user leaves a waitlist, and doing so closes the gap for everyone behind them
- [ ] Entries record the moment of joining, precisely enough that two entries made close
      together still have a definite order
- [ ] Another user's entry reports not-found, matching bookings
- [ ] The same date rules apply as booking: end on or after start, at most thirty days, no
      past-dated ranges
- [ ] Waitlist entries for a date range that has passed are inert and never offered
