# 27 — Availability search

**What to build:** A way to ask what can actually be booked before trying to book it.
Given a provider, a date range, and optionally a class, report which classes have a vehicle
free for the whole range and how many. Without this a user can only discover that something
is full by being refused.

**Blocked by:** 26

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] An authenticated user asks for availability by provider and date range
- [x] The response lists each vehicle class with the number of vehicles free for the whole
      requested range
- [x] A class with no free vehicle reports zero rather than being omitted, so a caller can
      tell "full" from "does not exist"
- [x] The same date rules as booking apply to the query: end on or after start, at most
      thirty days
- [x] Retired providers are excluded, matching the provider list
- [x] An unauthenticated caller is refused
- [x] The answer agrees with what booking actually does: if availability says zero, booking
      is refused, and if it says one, booking succeeds
- [x] The search is one query rather than one per class

## Notes

Route: `GET /providers/{provider_id}/availability?start_date=&end_date=`

Implemented in `app/providers/router.py`. Response shape is a list of
`{vehicle_class_id, name, free_count}` — schema `AvailabilityRow` in
`app/providers/schemas.py`.

**Retired provider → 404**, matching provider list behaviour. The dependency
`get_provider_or_404` returns retired providers by design (users need to see who they
booked with), so the retirement check is explicit in the handler.

**Date validation → 422** via `validate_rental_period` from `app/bookings/schemas.py`.
ValueError is caught and re-raised as HTTPException 422. The no-past-start rule from
booking creation does NOT apply here — the ticket only says "same date rules as booking",
which are end ≥ start and ≤ 30 days.

**One query** uses a four-CTE query: `days` generates the date series, `class_capacity`
aggregates vehicle counts, `daily_bookings` cross-joins days with classes then LEFT JOINs
bookings, `peak_bookings` takes the per-class maximum. `GREATEST(0, cap - peak)` guards
against a class that was over-booked before cars were removed.

No migration needed — pure query endpoint, no schema changes.
