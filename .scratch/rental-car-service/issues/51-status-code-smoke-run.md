# 51 — Status-code smoke run

**What to build:** One command that boots nothing, assumes a running app and a freshly
seeded database, and walks the whole service asserting **status codes only**. It exists to
catch a break, not to demonstrate behaviour — the demonstration is ticket 22's Postman
collection, and this is deliberately not that.

The reason it is its own ticket: three defects on this project were found by accident
rather than by checking. `app/seed.py` broke twice when a booking column became required
(tickets 25 and 29), and `OneWayRouteEnable` silently discarded a `relocation_fee` and
answered 200 (found while writing something unrelated). All three are first-failure
material for a run like this. Round two still has twenty-odd tickets to land against the
same booking model, so the gap is not going to stop mattering on its own.

**Why status codes only.** The response *shape* churns constantly — the booking body has
gained three fields since ticket 22 was written — but `201` stays `201` when a payload grows
a field. Asserting shapes would mean a run that fails every time anyone adds a column, which
is the kind of check people start ignoring. Asserting codes means a failure is always real.

**Blocked by:** None — every route it touches is already merged

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] One command, documented, needing no arguments: a running app on the default port and a
      freshly seeded database
- [x] Asserts status codes and nothing else. No assertions on response bodies beyond reading
      identifiers it needs for the next call
- [x] Discovers providers, classes, branches and one-way routes through the API rather than
      hardcoding seeded ids, so ticket 47 rebuilding the fixture does not break it
- [x] Computes every date through `today()` from `app/core/clock.py`, so it cannot disagree
      with the server about what day it is
- [x] Covers the negative cases that carry the rules: reversed dates, past-dated creation,
      the thirty-one-day rental, the fourth active booking, a retired provider, another
      provider's vehicle class, a non-existent class, a full class, an unenabled one-way
      direction, another user's booking, reviewing before the rental period ends, a second
      review on one booking, and a registered user on an admin-only route
- [x] Uses the seeded ended booking for the two rules that cannot be reached by API calls
      alone: that an ended booking stops counting toward the cap, and that it is reviewable
- [x] Verifies its own preconditions and **exits distinctly** when the database is not
      freshly seeded, rather than reporting false failures
- [x] Registers its own throwaway users instead of consuming the seeded ones, so the seeded
      accounts stay available for a live demo
- [x] Leaves the review count back at zero, so a demo can still perform the first review
- [x] Prints one line per check and a summary, and exits non-zero if any check failed
- [x] `docs/SPEC.md` says what this is and, explicitly, that it is not the automated test
      suite the project decided against — a one-command smoke run is not a unit-test suite,
      and the distinction has to be written down or the next reader will think the decision
      was quietly reversed
