# 14 — Demo seed data

**What to build:** One command that loads the system with a clean, known set of demo data
so the whole feature set can be shown from scratch. This has to include a booking whose
rental period has already ended, because reviewing requires one and the API deliberately
refuses to create past-dated bookings — so the seed writes it directly through the ORM,
bypassing a rule that exists to protect users rather than to constrain fixtures. Without
this ticket the review feature cannot be demonstrated at all.

**Blocked by:** 11, 13

**Owner:** Garfield

**Status:** done

- [x] One documented command loads all demo data
- [x] It creates three or four providers with realistic details, at least one of them
      retired, so retirement is visible in a demo
- [x] It creates the admin account, or works alongside the existing admin provisioning
      command without duplicating it
- [x] It creates two registered users: one with bookings ready to demonstrate, one clean
      for walking through registration and login
- [x] It creates, for the demo user, one booking whose rental period has already ended,
      written directly rather than through the API
- [x] It creates, for the same user, one upcoming booking
- [x] It creates no reviews, so that the demo writes the first one live
- [x] Re-running it produces the same state rather than duplicates
- [x] It refuses to run when the environment is production
- [x] All demo credentials are documented

## Notes

Implemented as `app/seed.py`, run with `uv run python -m app.seed`.

Idempotency is achieved by wiping all rows (bookings → providers → users, FK-safe order)
then recreating the fixed set. No upsert logic needed.

The ended booking is inserted directly through the ORM with past dates, bypassing the
no-past-dates validation rule as the ticket describes. `today()` from `app/core/clock.py`
is used for all relative date calculations so the seed respects the business timezone.

Demo credentials:
- Admin:      admin@example.com  / admin1234
- Demo user:  demo@example.com   / demo1234  (ended + upcoming booking)
- Clean user: fresh@example.com  / fresh1234 (no bookings)

`docs/SPEC.md` already described this command accurately; no changes were needed.
