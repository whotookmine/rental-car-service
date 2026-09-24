# 17 — Booking deletion cascades to its review

**What to build:** Deleting a booking takes its review with it, so that no review survives
without the rental that justified it. This is enforced by the database rather than by
application code — it is one of the reasons PostgreSQL was chosen over the document-store
option, and it must hold even for writes that bypass the API.

**Blocked by:** 15

**Owner:** Time

**Status:** done — verified against a running API and directly against PostgreSQL.

- [x] Deleting a booking that carries a review removes the review too
- [x] The cascade is declared on the foreign key, so it holds for direct database writes,
      not only for deletions made through the API
- [x] The provider's review count and average rating reflect the removal
- [x] Deleting a booking with no review still succeeds
- [x] A known and accepted consequence, which needs no mitigation: a user can erase their
      own unfavourable review by deleting the booking

## Notes

**No code was written for this ticket.** Ticket 15 already declared the cascade where it
belongs, so this was a verification ticket: the work was proving the criteria hold rather
than making them hold. That is worth recording, because "the API behaved correctly" would
not have been enough evidence on its own.

### Why the distinction mattered

The criterion asks for the cascade to be *on the foreign key*, not in application code.
SQLAlchemy can cascade in Python via `relationship(cascade="all, delete-orphan")`, and that
passes every API test while doing nothing for a direct database write — the two are
indistinguishable from outside. Checked both ways:

- The schema carries it: `reviews_booking_id_fkey FOREIGN KEY (booking_id) REFERENCES
  bookings(id) ON DELETE CASCADE`, and the migration that builds a fresh database declares
  `ondelete="CASCADE"`.
- There is no `relationship()` from `Booking` to `Review` at all, so Python could not be
  doing it even if the FK were wrong.
- **Deleting by raw SQL**, bypassing the ORM entirely, removed the review: `DELETE FROM
  bookings WHERE id = ...` left the reviews table at zero rows.

### The criteria

- Deleting a reviewed booking through the API answers 204 and takes the review with it.
- Deleting a booking with no review still answers 204 and touches nothing.
- The provider's figures move, and not only in the trivial one-to-zero case: a provider
  with reviews of 5, 4 and 3 reported `avg=4.0 count=3`; deleting the 5-star booking by raw
  SQL left `avg=3.5 count=2`. With the last review gone the average reports `null`, not
  zero, which is the distinction ticket 19 makes between untested and terrible.
- No orphaned rows: `select count(*) from reviews where booking_id not in (select id from
  bookings)` returns 0.
- The accepted consequence is real and was exercised deliberately: the owner left a 1-star
  review, deleted the booking, and the review was gone. A user can erase their own
  unfavourable review this way. The brief carries no anti-abuse requirement, so this stands
  as designed rather than as something to mitigate.

