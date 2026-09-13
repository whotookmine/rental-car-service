# 15 — Review creation

**What to build:** Once a rental is over, the person who rented rates the provider from 1
to 5 and says what the experience was like, so the next customer chooses better than the
last. Only the person who actually rented can review, only once the rental period has
ended, and only once per booking.

**Blocked by:** 14

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] The owner of a booking whose rental period has ended creates a review with a rating
      from 1 to 5 and a written comment
- [ ] Reviewing a booking whose rental period has not ended is refused as a conflict, not
      as malformed input — the request is well formed, the state is wrong
- [ ] A booking whose rental period ended today counts as ended, judged in the business
      timezone
- [ ] A second review on the same booking is refused as a conflict, enforced by a
      uniqueness constraint rather than by a check alone
- [ ] Reviewing another user's booking reports not-found, not forbidden
- [ ] A rating below 1 or above 5, or a non-integer rating, is rejected as unprocessable
- [ ] A user who rented the same provider twice can review each booking separately
- [ ] A provider that has since been retired is still reviewable by someone who booked it
- [ ] An unauthenticated caller is refused
