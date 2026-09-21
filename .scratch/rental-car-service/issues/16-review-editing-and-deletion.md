# 16 — Review editing and deletion

**What to build:** The author of a review can correct a mistake, change their mind, or
withdraw the opinion entirely — without having to destroy the booking to do it. The
requirements never grant this; it is granted deliberately, because deleting the booking
already gives users a destructive route to the same outcome, and offering the direct route
is better for the data.

**Blocked by:** 15

**Owner:** Garfield

**Status:** done

- [x] An author changes the rating and comment on their own review
- [x] Rating validation on edit matches creation
- [x] An author deletes their own review
- [x] Deleting a review leaves its booking intact
- [x] A booking whose review was deleted becomes reviewable again
- [x] The booking a review belongs to cannot be changed; a review can never be moved to a
      different booking
- [x] Editing or deleting another user's review reports not-found, not forbidden
- [x] An unauthenticated caller is refused

## Notes

New file: `app/reviews/dependencies.py` — `get_owned_review_or_404`.
Ownership resolves through the booking: review → booking.user_id == current_user.id.
Both other-user and admin cases return 404 (no admin-widened scope for reviews).

`PUT /reviews/{id}` uses `ReviewUpdate` schema with `extra="forbid"` and no `booking_id`
field, so sending one is rejected as 422 rather than silently ignored.

`DELETE /reviews/{id}` → 204. Booking survives; verified by fetching it after deletion.
Re-review after deletion → 201 confirmed.

`docs/SPEC.md` updated with edit/delete surface rules.
