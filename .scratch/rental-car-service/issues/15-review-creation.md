# 15 — Review creation

**What to build:** Once a rental is over, the person who rented rates the provider from 1
to 5 and says what the experience was like, so the next renter chooses better than the
last. Only the person who actually rented can review, only once the rental period has
ended, and only once per booking.

**Blocked by:** 14

**Owner:** Garfield

**Status:** done

- [x] The owner of a booking whose rental period has ended creates a review with a rating
      from 1 to 5 and a written comment
- [x] Reviewing a booking whose rental period has not ended is refused as a conflict, not
      as malformed input — the request is well formed, the state is wrong
- [x] A booking whose rental period ended today counts as ended, judged in the business
      timezone
- [x] A second review on the same booking is refused as a conflict, enforced by a
      uniqueness constraint rather than by a check alone
- [x] Reviewing another user's booking reports not-found, not forbidden
- [x] A rating below 1 or above 5, or a non-integer rating, is rejected as unprocessable
- [x] A user who rented the same provider twice can review each booking separately
- [x] A provider that has since been retired is still reviewable by someone who booked it
- [x] An unauthenticated caller is refused

## Notes

New files: `app/reviews/models.py`, `app/reviews/schemas.py`, `app/reviews/router.py`.
Route: `POST /bookings/{booking_id}/reviews`.

The `get_visible_booking_or_404` dependency from bookings already handles 404 for a regular
user reaching another user's booking. An admin can see any booking through that dependency,
so an explicit `booking.user_id != current_user.id` check in the handler covers the admin
case too — both return 404, consistent with the ownership-protection principle.

The "ended today" rule: check is `booking.end_date >= today()` → 409. If end_date equals
today, the rental has ended today, so `end_date < today()` is false → not a conflict.

Duplicate enforcement is at the DB level (unique index on `booking_id`). The IntegrityError
is caught and converted to 409 so the constraint is the authority, not a pre-check race.

Alembic migration: `70335458633a_add_reviews_table.py`. Round-trip verified.
`app/db/base.py` import uncommented; router registered in `app/main.py`.
`docs/SPEC.md` updated with Review surface section.
