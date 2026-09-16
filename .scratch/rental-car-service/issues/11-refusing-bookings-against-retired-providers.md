# 11 — Refusing bookings against retired providers

**What to build:** A registered user cannot reserve with a provider that has stopped
trading. This is the point of retirement: existing bookings run their course, but no new
ones are taken.

**Blocked by:** 07, 08

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] Creating a booking against a retired provider is refused as a conflict
- [ ] The refusal message names the reason, so the user is not left guessing
- [ ] Bookings created before the provider was retired are unaffected and remain viewable
- [ ] Reinstating a provider makes it bookable again

## Heads-up from ticket 08 (Time → Garfield)

I touched `app/providers/` while finishing ticket 08. Nothing about ticket 11 changes, but
read this before you start.

**What changed.** The `db.get(Provider, ...)` then 404 block appeared six times across the
providers and bookings packages, and ticket 11 would have added a seventh. It is now one
dependency, `get_provider_or_404` in `app/providers/dependencies.py`, used by every route
that addresses a provider by identifier: the four in `app/providers/router.py` and booking
creation. Those routes now take `provider: Provider = Depends(get_provider_or_404)`
instead of an untyped `provider_id: int` plus their own lookup.

**What it means for you.** Booking creation already has the `Provider` object in hand, so
this ticket is a single `is_retired` check and a 409 — no lookup to write.

**A bug I introduced and fixed, worth knowing about.** Making the lookup a parameter
dependency meant FastAPI resolved it *before* the route's own auth dependency, so
`PATCH /providers/999` from an unauthenticated caller answered 404 instead of 401 — an
anonymous caller could learn which provider identifiers exist. `get_provider_or_404` now
depends on `get_current_user` itself, so authentication always resolves first. Reordering
the parameters would also have worked and would have broken the moment someone reordered
them. If you add another dependency that reads the database, check the same thing.

**Verified after the change**, so you are not inheriting a regression: every acceptance
criterion of tickets 05, 06 and 07 still passes, including that a registered user sending
`include_retired=true` is still given only active providers.

**Unrelated, noticed while testing:** `GET /providers` has no `ORDER BY`, so the list comes
back in whatever order PostgreSQL feels like — it visibly changed between runs. Not yours
to fix here; flagged on ticket 19, which rebuilds that query anyway.

