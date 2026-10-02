# Handover — Time to Garfield, 2026-10-02

Everything on my side is merged and pushed to `origin/main`. **All eight remaining tickets are
yours**, and three of them can start right now.

Read `docs/REQUIREMENTS-TRACE.md` first. It holds the requirements as we were actually given
them, verbatim, mapped clause by clause to the route that satisfies it and the check that
proved it. It is the document to hold a demo against, and it is what I would read if I were
picking this up cold.

## Where the requirements stand

| | Requirement | State |
|---|---|---|
| Round one | registration, login, bookings, admin oversight, reviews, ratings | **Complete** — except the Postman collection, which is ticket 22 |
| 4 | waitlist, FIFO release, notification, claim window, pass-on | **Complete** (tickets 42–46) |
| 5 | one-way rentals | Built **except the relocation fee** — ticket 35 |
| 6 | delivery and collection | **Nothing built** — tickets 36, 37, 38 |
| 7 | maintenance blackouts | **Complete** (tickets 39–41) |

## Start now — all three are unblocked

**22 — Postman collection and README.** The only deliverable the requirements name by name
("the system shall be used and tested via Postman"), and the only round-one clause still
missing. I would do this first regardless of what else happens: it is the thing a grader opens.
Two notes already on the ticket — the booking body is bigger than round one describes, and
seeded dates are relative to the day the seed runs, so compute dates in pre-request scripts.

**35 — relocation fee.** The last clause of an otherwise finished requirement, so requirement 5
currently reads half-done. Both halves it needs already exist: the distances from ticket 30 and
the quotation from ticket 34. I left the verification on the ticket showing the quotation
returning only the rental line.

**36 — delivery radius.** The head of the requirement-6 chain.

## Then, in this order

```
36 → 37 → 38 → 47 → 48 → 49
```

47 was blocked on my work and no longer is — ticket 41 landed blackout enforcement and ticket 46
closed the waitlist, so a fixture can seed both a blacked-out vehicle and a waiting queue. It is
still blocked on **38**, so requirement 6 has to land first.

## Things that will bite you if nobody says them

**`_WIPE_ORDER` in `app/seed.py`.** Any new table that references an existing one with
`ON DELETE RESTRICT` has to be listed there, above the table it points at, or
`uv run python -m app.seed` dies. This has broken three times — tickets 25, 29 and 39 — and only
the third was caught before merging. Run the seed before closing any ticket that adds a table or
touches a model.

**`uv run python -m app.smoke`.** 182 status-code checks across the whole service, about ten
seconds, repeatable without re-seeding. Run it before closing anything. It is not the automated
suite we decided against — see the Verification table in `docs/SPEC.md` — and it does not replace
exercising your own ticket by hand; it catches what your ticket broke somewhere else. Exit `2`
means re-seed, not failure. Please add checks for your routes as you go; every ticket of mine did.

**One home for "is this class full": `measure_room` in `app/bookings/rules.py`.** Booking,
availability and the waitlist all read it. Ticket 40 is why — the same arithmetic in two places
disagreed within one ticket, and ticket 41 had to close the gap. If delivery ever needs to ask
whether a car is available, ask that function; do not write a fourth version.

**Lock order is owner → vehicle class → vehicle.** Every path that takes more than one takes
them that way round. There is exactly one recorded exception — converting a waitlist claim holds
the class and then takes the owner — and `docs/SPEC.md` names it as the route to revisit if
anything new takes a lock. Two paths in opposite orders is how a deadlock is built.

**Nest a summary, not a read shape.** A resource nested inside another carries **stored columns
only**, never a field computed by aggregation. `ProviderSummary` and `VehicleClassSummary` exist
for this. We paid for the rule twice: every booking reported a confident "never reviewed" for a
four-star provider (ticket 50), and the waitlist reported `offered_at: null` while the database
held a timestamp (ticket 44). Both were a response shape quietly defaulting a field nobody
filled in.

**Alembic autogenerate cannot be trusted blindly.** Three times now: it misreports functional
unique indexes, it omitted the `btree_gist` extension the blackout exclusion constraint depends
on, and it emitted an **unnamed** foreign key with a `drop_constraint(None, ...)` downgrade that
cannot work. Always read the generated file, and always check `downgrade -1` and back up, not
just a full rebuild from empty.

**`CLAIM_WINDOW_MINUTES`** is configuration, default 60. Set it to `1` in the demo walkthrough if
you want a grader to watch a claim expire without waiting an hour.

**New since you last looked:** `app/core/clock.py` now has `now()` beside `today()` — instants
for events, dates for domain periods, and picking the wrong one is a bug in both directions. The
docstring explains it and names the one exempt module.

## For ticket 47 specifically

- The fixture needs a **blacked-out vehicle** and a **populated queue**. Joining a queue is
  refused unless the class is full for those dates, so the fixture has to book the class out
  first, exactly as a user would. Writing the rows straight through the ORM bypasses that check,
  which is fine for a fixture — but the seeded state should still be one the API would have
  allowed, or the demo contradicts the rules.
- **Black out a car in a class the walkthrough does not book.** Blacking out one of the three
  Economy cars makes that class refuse a third concurrent booking, which will surprise whoever
  writes the walkthrough in 48.
- Converted and declined waitlist entries stay in the table by design — they are the record of
  what happened — and they hold a `RESTRICT` key to their class.

## State of the tree

`main` is clean and pushed. The schema rebuilds from empty, `alembic check` reports no drift, the
seed runs, and `app/smoke.py` reports 182/182 twice in a row without re-seeding. Port 8000 is
free.

Ping me if any of the above turns out to be wrong rather than working around it — a document that
says something untrue has been this project's most repeated failure, and I would rather fix it
than have you route around it.
