# 21 — Admin review deletion

**What to build:** An admin removes a review that should not stand, so abusive content
does not stay visible against a provider. Removing bad content must not destroy the
owner's rental record, and they should be able to write a proper review
afterwards.

**Blocked by:** 15

**Owner:** Garfield

**Status:** done

- [x] An admin deletes any review, not only their own
- [x] The booking the review belonged to survives intact
- [x] That booking becomes reviewable again, and its owner can write a new review
- [x] The provider's average rating and review count update to reflect only reviews that
      still stand
- [x] A registered user attempting to delete someone else's review is still refused
- [x] Deleting a review never deletes a booking; the relationship runs one way only

## Notes

Added `get_deletable_review_or_404` to `app/reviews/dependencies.py`. Admins access any
review; regular users are still scoped to their own (404 for another user's review).

`DELETE /reviews/{id}` now uses `get_deletable_review_or_404`; `PUT /reviews/{id}` keeps
`get_owned_review_or_404` (edit remains owner-only, per the SPEC).

`docs/SPEC.md` updated to reflect the split: edit = owner only, delete = owner or admin.
