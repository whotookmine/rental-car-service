# 21 — Admin review deletion

**What to build:** An admin removes a review that should not stand, so abusive content
does not stay visible against a provider. Removing bad content must not destroy the
customer's rental record, and the customer should be able to write a proper review
afterwards.

**Blocked by:** 15

**Status:** ready-for-agent

- [ ] An admin deletes any review, not only their own
- [ ] The booking the review belonged to survives intact
- [ ] That booking becomes reviewable again, and its owner can write a new review
- [ ] The provider's average rating and review count update to reflect only reviews that
      still stand
- [ ] A registered user attempting to delete someone else's review is still refused
- [ ] Deleting a review never deletes a booking; the relationship runs one way only
