# 13 — Booking deletion and slot release

**What to build:** A registered user cancels a trip by deleting the booking, and can
immediately book again in its place. Deletion is literal — there is no cancelled state
and no soft delete for bookings.

**Blocked by:** 10, 12

**Owner:** Time

**Status:** ready-for-agent

- [ ] An owner deletes their own booking and it is gone from their list
- [ ] A user holding three active bookings can create a new one immediately after
      deleting any of them
- [ ] Deleting another user's booking reports not-found, not forbidden
- [ ] Deleting a booking that does not exist reports not-found
- [ ] The booking row is removed rather than flagged
- [ ] An unauthenticated caller is refused
