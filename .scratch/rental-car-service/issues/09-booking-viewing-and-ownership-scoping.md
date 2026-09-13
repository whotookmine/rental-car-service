# 09 — Booking viewing and ownership scoping

**What to build:** A registered user sees what they have reserved, and cannot see anyone
else's. Reaching for another user's booking reports not-found rather than forbidden, so
that booking identifiers cannot be enumerated to measure how much other people are
renting.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] A registered user lists their own bookings and only their own
- [ ] A registered user fetches one of their own bookings by identifier
- [ ] Each booking carries its rental period and the provider it is with, including that
      provider's contact details
- [ ] Fetching another user's booking reports not-found, not forbidden
- [ ] Fetching a booking that does not exist reports not-found, indistinguishably
- [ ] A user with no bookings receives an empty list rather than an error
- [ ] An unauthenticated caller is refused
