# 12 — Booking re-dating

**What to build:** A registered user adjusts their plans by changing a booking's dates,
including extending one that is already underway. Which provider the booking is with can
never change, so that every booking keeps reflecting the company actually reserved with —
this is what keeps a review attached to the right provider.

**Blocked by:** 09

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] An owner changes the start and end dates of their own booking
- [x] The same rules as creation apply: end on or after start, and at most thirty days
- [x] Unlike creation, a start date in the past is permitted, so that a booking already
      underway can be extended and history can be corrected
- [x] The three-active-booking cap is re-checked, so a user cannot edit their way past it
- [x] The provider cannot be changed; an attempt to change it is refused or ignored, never
      silently applied
- [x] Editing another user's booking reports not-found, not forbidden
- [x] Editing a booking that does not exist reports not-found
- [x] An unauthenticated caller is refused

## Notes

- `PUT /bookings/{booking_id}`, not PATCH. A rental period is one value with two halves,
  so replacing it wholesale keeps both date rules on the request schema where they answer
  422, rather than pushing them into the handler to validate a merge of old and new values.
  Provider editing uses PATCH because its fields are genuinely independent; this is not.
- The two shape rules — end on or after start, at most thirty days — now live in one
  `validate_rental_period` function that creation and re-dating both call. The no-past-dates
  rule stays on creation alone. Ticket 08 predicted this split and left the pieces
  module-level so it would be cheap; it was.
- Verified live: a past start date is accepted on re-dating and still refused on creation,
  which is the whole point of the split.
- The provider is refused, not ignored: `{"provider_id": 2}` returns 422 and the booking
  still points at provider 1, checked afterwards rather than assumed.
- Ownership and existence both answer 404, an out-of-range identifier answers 422, and an
  unauthenticated caller 401.

### The cap interaction, which is subtler than it looks

Three separate behaviours, all verified:

- A user **at** the cap can still edit their bookings. The booking being changed is excluded
  from its own count, or holding the maximum would freeze them.
- A user at the cap **cannot extend an ended booking into the future**, because that would
  be a fourth active booking. This is the "cannot edit their way past the cap" criterion,
  and it needed an ended booking written through the ORM to test, since the API will not
  create one.
- A user at the cap **can** edit an ended booking that stays ended, because it occupies no
  slot. The cap is only re-checked when the new dates would leave the booking active.

`excluding_booking_id` is back on the counting rule. Ticket 10 removed it as speculative
generality because nothing used it; it is real now.

Re-dating goes through the same `ensure_room_for_another_booking`, so it inherits the
owner-row lock added after the audit. Confirmed under concurrency: starting at two active
bookings, four simultaneous attempts produced one insert and three 409s.
