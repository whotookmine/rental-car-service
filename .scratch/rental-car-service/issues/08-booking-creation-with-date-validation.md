# 08 — Booking creation with date validation

**What to build:** A registered user reserves a car by booking a provider for a rental
period, giving a start and an end date. The system refuses rental periods that make no
sense. Start and end are plain dates with no time component, and every comparison against
today uses the business-timezone helper rather than the system clock.

**Blocked by:** 06

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] A registered user creates a booking against a provider for a start and end date
- [x] The booking is created under the provider, which cannot be omitted
- [x] The created booking records its owner from the token, never from the request body
- [x] A rental period with the same start and end date is accepted as a one-day rental
- [x] An end date before the start date is rejected as unprocessable
- [x] A rental period longer than thirty days is rejected as unprocessable
- [x] A start date in the past is rejected as unprocessable
- [x] A start date of today is accepted
- [x] Booking against a provider that does not exist reports not-found
- [x] An unauthenticated caller is refused
- [x] Dates are stored as dates with no time component, and "today" is computed in the
      configured business timezone

## Notes

- Verified live on a freshly migrated database: a normal booking, a one-day rental
  (start equal to end), a rental starting today, and one of exactly thirty days are all
  accepted. End before start, thirty-one days, a start date in the past, a malformed date,
  a datetime carrying a time component, a missing field, and a body-supplied `user_id` are
  all 422. An unknown provider is 404 and an unauthenticated caller is 401.
- The thirty-day cap counts inclusively, matching the Rental Period definition in
  `CONTEXT.md`: a booking from the 1st to the 30th is thirty days. The naive
  `(end - start).days` would have let a thirty-one-day rental through.
- The owner is taken from the access token. Verified by booking as a second user and
  confirming the stored `user_id` was theirs, and `extra="forbid"` rejects a body that
  tries to name someone else rather than ignoring it.

### Deliberately not in this ticket

Both were confirmed still absent by testing for them, so a later ticket cannot assume
they already exist:

- Refusing a booking against a **retired** provider is ticket 11. A retired provider is
  still bookable today.
- The **three-active-booking cap** is ticket 10. A fifth booking still succeeds.

### For later tickets

- A request that is both badly dated and names a provider that does not exist answers
  422, not 404, because validation runs before the handler. Ticket 22's Postman collection
  should not assume the other order.
- All three date rules live in one validator on `BookingCreate`, but ticket 12 needs only
  two of them: re-dating shares date ordering and the thirty-day maximum, and deliberately
  does not share the no-past-dates rule. `rental_period_days` and `MAX_RENTAL_DAYS` are
  module-level so that split stays cheap.
- The `db.get(Provider, ...)` then 404 block appeared six times across the providers and
  bookings packages. It was left alone in the first commit because extracting it edits a
  teammate's module mid-ticket; it **was** extracted in this ticket's closeout once that
  was agreed, into `get_provider_or_404`, and is now the single home for the lookup.
  See "Corrected after audit" below for the leak that extraction introduced and how it was
  closed.

### Later change

Ticket 09 changed `BookingRead` to nest the full provider instead of a bare `provider_id`,
so that a booking reports who it is with wherever it appears. Creation returns that shape
too. Behaviour here is unchanged and was re-verified after the change.

### Corrected after audit

Two problems in this ticket's code, both found by audit rather than by the original review:

- **Admins could hold bookings.** `docs/SPEC.md` and `CONTEXT.md` both say they do not, and
  nothing enforced it — an admin token created a booking successfully. Creation now depends
  on `require_registered_user` and refuses an admin with 403.
- **An out-of-range integer id returned 500.** A path id larger than an integer primary key
  can hold reached PostgreSQL and raised `NumericValueOutOfRange`, breaking the uniform
  error contract. Provider and booking id path parameters are now bounded, so those answer
  422.

Also corrected here: the `get_provider_or_404` extraction made by this ticket's closeout
left `require_admin` resolving *after* the lookup on admin-only provider routes, so a
registered user hitting a missing provider saw 404 before 403 — the mirror image of the
401-before-404 discipline the same commit was written to establish. The admin check now
comes first, with a comment on the router saying why the order matters.
