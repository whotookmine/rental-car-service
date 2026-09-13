# 14 — Demo seed data

**What to build:** One command that loads the system with a clean, known set of demo data
so the whole feature set can be shown from scratch. This has to include a booking whose
rental period has already ended, because reviewing requires one and the API deliberately
refuses to create past-dated bookings — so the seed writes it directly through the ORM,
bypassing a rule that exists to protect users rather than to constrain fixtures. Without
this ticket the review feature cannot be demonstrated at all.

**Blocked by:** 11, 13

**Status:** ready-for-agent

- [ ] One documented command loads all demo data
- [ ] It creates three or four providers with realistic details, at least one of them
      retired, so retirement is visible in a demo
- [ ] It creates the admin account, or works alongside the existing admin provisioning
      command without duplicating it
- [ ] It creates two registered users: one with bookings ready to demonstrate, one clean
      for walking through registration and login
- [ ] It creates, for the demo user, one booking whose rental period has already ended,
      written directly rather than through the API
- [ ] It creates, for the same user, one upcoming booking
- [ ] It creates no reviews, so that the demo writes the first one live
- [ ] Re-running it produces the same state rather than duplicates
- [ ] It refuses to run when the environment is production
- [ ] All demo credentials are documented
