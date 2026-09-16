# 09 — Booking viewing and ownership scoping

**What to build:** A registered user sees what they have reserved, and cannot see anyone
else's. Reaching for another user's booking reports not-found rather than forbidden, so
that booking identifiers cannot be enumerated to measure how much other people are
renting.

**Blocked by:** 08

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] A registered user lists their own bookings and only their own
- [x] A registered user fetches one of their own bookings by identifier
- [x] Each booking carries its rental period and the provider it is with, including that
      provider's contact details
- [x] Fetching another user's booking reports not-found, not forbidden
- [x] Fetching a booking that does not exist reports not-found, indistinguishably
- [x] A user with no bookings receives an empty list rather than an error
- [x] An unauthenticated caller is refused

## Notes

- Verified live with three users: Alice lists only her two bookings, Bob lists only his
  one, and Carol, who has none, gets an empty list with 200 rather than an error.
- The 404s are **byte-identical**. Bob fetching Alice's booking and Bob fetching a booking
  that does not exist return the same status and the same body, checked by comparing the
  two responses directly rather than by eye. Anything less and the identifiers could be
  walked to count how much other people rent.
- Ownership is enforced in the query for the list and in `get_own_booking_or_404` for the
  detail route, so there is no parameter a caller could pass to widen the scope.
- The scoped lookup is a shared dependency from the start: tickets 12 and 13 re-date and
  delete through the same rule, and ticket 08 already showed what happens when this kind of
  block is copied per route.
- Following the ticket 08 lesson, the dependency takes `get_current_user`, so an
  unauthenticated caller gets 401 before any lookup can answer 404.
- The list is explicitly ordered by rental period start. Without an `ORDER BY`, PostgreSQL
  returns rows in an order that changes between runs — which is the same problem flagged
  on ticket 19 for the provider list.

### Shape change affecting ticket 08

`BookingRead` now nests the full provider instead of carrying a bare `provider_id`,
because this ticket requires a booking to report "the provider it is with, including that
provider's contact details". Booking creation returns the same shape, so a booking looks
the same everywhere it appears. Ticket 08's behaviour is unchanged and was re-verified;
only the response body grew.

The relationship is loaded with a join, so listing bookings is one query rather than one
per booking. Confirmed by counting the statements the list issues: two bookings, one
SELECT.
