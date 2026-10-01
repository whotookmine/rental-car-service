# Rental Car Service — working agreement

A REST API where registered users book rental car providers for a period and review them
afterwards. Backend only; there is no frontend.

## Read these first, in this order

| File | What it is | Standing |
|---|---|---|
| `CONTEXT.md` | The glossary. Booking, Rental Period, Active Booking, Provider, Retired Provider, Review, Registered User, Admin. | Use these words in code, routes, and responses. The `_Avoid_` lists are words that must not appear. |
| `docs/REQUIREMENTS-TRACE.md` | The requirements **as given**, verbatim, mapped clause by clause to the route that satisfies it and the check that proved it. Names what is still missing. | The brief. This is what the work is graded against. Re-audit it whenever a clause changes state. |
| `docs/SPEC.md` | The agreed ruleset: entities, date semantics, validation, status codes. | Binding. If the code and this disagree, one of them is a bug. |
| `docs/adr/` | Decisions that are expensive to reverse, each with its reasoning. | Binding. Do not quietly work around an ADR. |
| `.scratch/rental-car-service/spec.md` | The same design in problem-and-user-story form. | Context, not law. |

This brief is a re-skin of a common appointment-booking exercise. Vocabulary from that
lineage — appointments, hospitals, vacancies — must never appear in this codebase.

## Tickets

Work is 22 numbered tickets in `.scratch/rental-car-service/issues/`, each a vertical
slice that is demoable on its own. Every ticket file carries:

- **What to build** — the behaviour, from the user's point of view
- **Blocked by** — the tickets that must land first, or "None"
- **Owner** — Time or Garfield
- **Status** — `ready-for-agent` while open; set to `done` when merged
- A checklist of acceptance criteria

### The loop

1. **Pick from the frontier.** A ticket is available when every ticket in its "Blocked by"
   line is done. Take your own; do not take your teammate's without saying so.
2. **Read the ticket, the glossary, and any ADR that touches the area.** The acceptance
   criteria are the definition of done — not your reading of the requirement.
3. **Branch**: `feat/NN-short-slug` off `main`.
4. **Build only that ticket.** See Scope, below.
5. **Verify by running it**, not by reading it. See Verification, below. If the ticket
   touched a model, run `uv run python -m app.seed` as part of that: the fixture writes
   rows through the ORM rather than the API, so a newly required column breaks it silently
   until someone tries to demo. It has already happened twice.
6. **Tick the boxes and set `Status: done`** in the ticket file, in the same branch. Add a
   `## Notes` section for anything a reader would otherwise have to rediscover: judgement
   calls, deviations, things deliberately left out, things found while testing.
   **In the same commit, update `docs/SPEC.md`** if the ticket added a route, changed a
   status code, or made a rule behave differently from how the document describes it. This
   has been the single most repeated failure on this project: the code was right, the
   ticket Notes explained it, and the binding document was left saying something untrue.
   Notes are not a substitute — `docs/SPEC.md` is what the next person reads.
   **If the ticket closes a clause of the original brief, update
   `docs/REQUIREMENTS-TRACE.md` in the same commit too** — move the row from missing to
   verified, and paste the output that proves it. That file is what the work is graded
   against, and a row that still says "not built" about finished work costs marks.
7. **Merge to `main` and push.** Tell your teammate when a ticket they are blocked on lands.

### Scope

Implement the ticket in front of you and nothing else. Do not build the next ticket
because it is nearby, do not add models an upcoming ticket will need, do not add a
framework because it might help later. If something outside the ticket seems necessary,
the default is to leave it out and say so in the ticket's Notes.

Two exceptions, both narrow:

- Something the ticket's own criteria cannot be **verified** without. The health check in
  ticket 01 had to really query the database; the guard in ticket 03 needed an endpoint
  that revealed the caller.
- A security hole that the ticket's own work would otherwise leave open. Ticket 03 added a
  minimum length for the signing key, because a short key makes every guard in that ticket
  worthless.

Take an exception loudly: say so in the Notes and in the commit message.

### When the spec is wrong

`docs/SPEC.md` and the ADRs were written before the code existed, so occasionally reality
disagrees — a named library turns out to be abandoned, a rule contradicts another rule.
Do not silently do something different. Fix the document in the same commit, with the
reason, so it never says something untrue. A ticket's Notes should record it too.

## Verification

There is **no automated test suite**, by deliberate decision recorded in `docs/SPEC.md`.
Verification is manual, and the standard is higher because of it: never report a criterion
as met on code you have not run.

For each ticket, against a running app and a real database:

- Bring the database up, apply migrations from empty, start the app.
- Exercise every acceptance criterion, **including the negative cases** — wrong role,
  missing token, another user's record, malformed input, the boundary value.
- Check the migration round-trips: `upgrade` → `downgrade base` → `upgrade`, then
  `alembic check` for drift.
- Paste real command output when reporting. If something does not work, say so.

Credentials must never appear in a response body. Passwords, hashes, tokens belonging to
someone else. This has already been a live defect once: validation errors echoed the
rejected password until a handler was added to redact it.

## Stack and conventions

- **Python, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, PostgreSQL.** ADRs 0001 and
  0002 explain why, including why not MongoDB.
- **uv** manages dependencies. `uv add <pkg>`, `uv sync`, `uv run <cmd>`. `uv.lock` is
  committed. Never `pip install` into `.venv` — it drifts from the lock.
- **Feature-first layout**: one package per area, each owning its model, schemas, router
  and rules. Register every new model in `app/db/base.py` or migrations will not see it.
- **snake_case bare resources.** FastAPI's default `{"detail": ...}` error shape. No
  success/data envelope.
- **Dates are dates**, with no time component. Every comparison against "now" goes through
  `today()` in `app/core/clock.py`, which uses the configured business timezone. Calling
  `date.today()` anywhere else is a bug: the service runs seven hours ahead of UTC, so the
  two disagree for part of every day.
- **Status codes**: 409 when the request is well formed but the state is wrong; 422 for
  malformed input; 404 — not 403 — when a user reaches for another user's booking, so that
  identifiers cannot be enumerated. 403 is correct for admin-only routes, which hide
  nothing. The full table is in `docs/SPEC.md`.
- **Every request schema sets `extra="forbid"`, and every id it accepts is bounded
  `Field(ge=1, le=2147483647)`.** Both have been live defects: a silently discarded field
  the caller thought they had set, and an over-large id reaching PostgreSQL as a 500.
- **Identity comes from the access token only.** Never from a request body, a query
  parameter, or a header the client chooses the meaning of.
- One rule, one home. A rule enforced in two places will drift — as the password rule did,
  until registration and the admin command were made to share it.

## Commands

```bash
uv sync                                  # install from the lockfile
docker compose up -d                     # per-developer PostgreSQL
uv run alembic upgrade head              # apply migrations
uv run python -m app.create_admin        # provision an admin (no API route does this)
uv run uvicorn app.main:app --reload     # run the API
```
