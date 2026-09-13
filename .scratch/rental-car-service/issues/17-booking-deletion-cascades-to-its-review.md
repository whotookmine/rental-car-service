# 17 — Booking deletion cascades to its review

**What to build:** Deleting a booking takes its review with it, so that no review survives
without the rental that justified it. This is enforced by the database rather than by
application code — it is one of the reasons PostgreSQL was chosen over the document-store
option, and it must hold even for writes that bypass the API.

**Blocked by:** 15

**Status:** ready-for-agent

- [ ] Deleting a booking that carries a review removes the review too
- [ ] The cascade is declared on the foreign key, so it holds for direct database writes,
      not only for deletions made through the API
- [ ] The provider's review count and average rating reflect the removal
- [ ] Deleting a booking with no review still succeeds
- [ ] A known and accepted consequence, which needs no mitigation: a user can erase their
      own unfavourable review by deleting the booking
