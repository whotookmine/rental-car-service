# PostgreSQL over MongoDB Atlas

The course constraint permits either MongoDB Atlas or PostgreSQL, and the surrounding
course material assumes Express + Mongoose, so MongoDB is the path of least resistance.
We chose PostgreSQL anyway because the three hardest rules in this brief are all
relational problems that Postgres solves declaratively and MongoDB makes us hand-roll:
deleting a booking must cascade to its review, provider list responses must carry an
average rating and review count aggregated across reviews, and the "at most three active
bookings" check is a count-then-insert race that needs a real transaction.

## Consequences

- We are off the course's well-trodden path, so TA and classmate help will be less
  directly applicable. This is accepted deliberately; it is an operational cost, not a
  technical one.
- Referential integrity for the booking-to-review cascade is enforced by the database
  rather than by application code, and cannot be bypassed by writing to the DB directly.
