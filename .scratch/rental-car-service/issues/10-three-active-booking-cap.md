# 10 — Three-active-booking cap

**What to build:** A registered user may hold at most three active bookings — bookings
whose rental period has not yet ended. A fourth is refused with a message that explains
the limit rather than leaving the user guessing. Bookings whose periods have ended stop
counting, so past rentals do not permanently consume the allowance.

**Blocked by:** 08

**Status:** ready-for-agent

- [ ] A registered user can hold three active bookings
- [ ] A fourth active booking is refused as a conflict, not as malformed input
- [ ] The refusal message states that the user already holds three active bookings
- [ ] A booking whose rental period has ended does not count toward the limit
- [ ] The count is measured against the booking's owner, not the caller
- [ ] Two bookings with overlapping rental periods are permitted, since no vehicle
      inventory is modelled and the cap already bounds abuse
- [ ] The limit is counted using the business-timezone helper, not the system clock
