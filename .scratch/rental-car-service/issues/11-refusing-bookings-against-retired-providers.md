# 11 — Refusing bookings against retired providers

**What to build:** A registered user cannot reserve with a provider that has stopped
trading. This is the point of retirement: existing bookings run their course, but no new
ones are taken.

**Blocked by:** 07, 08

**Status:** ready-for-agent

- [ ] Creating a booking against a retired provider is refused as a conflict
- [ ] The refusal message names the reason, so the user is not left guessing
- [ ] Bookings created before the provider was retired are unaffected and remain viewable
- [ ] Reinstating a provider makes it bookable again
