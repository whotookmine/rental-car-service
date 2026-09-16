# 13 — Booking deletion and slot release

**What to build:** A registered user cancels a trip by deleting the booking, and can
immediately book again in its place. Deletion is literal — there is no cancelled state
and no soft delete for bookings.

**Blocked by:** 10, 12

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] An owner deletes their own booking and it is gone from their list
- [x] A user holding three active bookings can create a new one immediately after
      deleting any of them
- [x] Deleting another user's booking reports not-found, not forbidden
- [x] Deleting a booking that does not exist reports not-found
- [x] The booking row is removed rather than flagged
- [x] An unauthenticated caller is refused

## Notes

- `DELETE /bookings/{booking_id}` answers 204 with no body. Provider deletion answers 200
  with the record because it retires rather than removes; this one really deletes, so there
  is nothing to return.
- Verified live: Alice at the cap deletes one booking, is immediately able to create
  another, and is then refused again at the cap. The slot is released by the deletion
  itself, not by anything expiring.
- The row is gone, confirmed by reading the table rather than by trusting the API. The
  `bookings` table has exactly `id, user_id, provider_id, start_date, end_date` — no
  `deleted_at`, no `is_deleted`, no status column anywhere for a soft delete to hide in.
- Deleting another user's booking and deleting one that does not exist return
  **byte-identical** 404s, compared directly. The same discipline as fetching, for the same
  reason: otherwise the identifiers can be walked.
- A deleted booking is 404 on every subsequent verb — fetch, re-date, and delete again.
- An out-of-range identifier answers 422 rather than 500, inherited from the shared lookup
  fixed after the audit.
- Bob's booking was untouched throughout, so deletion is scoped as tightly as reading.

### Not in this ticket

Deleting a booking must also delete its review, at the database level. That is ticket 17,
and reviews do not exist yet. When the foreign key gains its cascade, this route needs no
change — which is the point of letting the database own that rule.
