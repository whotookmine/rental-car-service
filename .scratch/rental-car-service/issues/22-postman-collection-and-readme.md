# 22 — Postman collection and README

**What to build:** The deliverable the requirements actually name: a committed Postman
collection through which the whole system is exercised, plus documentation for standing it
up and walking through a demo. Since there is no automated test suite, this collection is
the only verification the project has — so its negative cases matter more than its happy
paths.

**Blocked by:** 16, 17, 18, 19, 20, 21

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] A collection is committed to the repository, organised by area: authentication,
      provider browsing, booking lifecycle, reviews, and admin
- [ ] Every request asserts on its status code and on the fields that distinguish success
      from the failure modes below
- [ ] Dates are computed in pre-request scripts relative to the current date and never
      hardcoded, so the collection does not go stale and start failing silently
- [ ] The token is captured from the login response into a collection variable and reused,
      so the collection runs end to end without manual copying
- [ ] The base URL is a variable, not a literal
- [ ] Negative cases are present explicitly: the fourth active booking, the reversed date
      range, the thirty-one-day rental, the past-dated creation, booking a retired
      provider, reviewing before the rental period ends, a second review on one booking,
      and one user reaching for another user's booking
- [ ] The two rules that cannot be verified by API calls alone — that an ended booking
      stops counting toward the cap, and that an ended booking becomes reviewable — are
      demonstrated using the seeded ended booking, and the collection says so where they
      appear
- [ ] The collection runs green end to end against a freshly seeded database
- [ ] The README covers setup, environment variables, running migrations, seeding, demo
      credentials, and a step-by-step demo walkthrough
- [ ] The README states that logout is client-side and invalidates nothing server-side, so
      it does not read as a defect
- [ ] Every response observed in the collection arrives well within three seconds

## Note from Time — 2026-10-02: this is the only round-one gap left

I audited the whole service against the requirements as originally given and wrote the
result up in `docs/REQUIREMENTS-TRACE.md`. Everything in round one passes against a running
app **except this ticket**.

That matters more than its position in the list suggests. *"The system shall be used and
tested via Postman"* is a non-functional requirement in the brief — the only deliverable
the requirements name by name. Every other clause is satisfied by behaviour a grader has to
go looking for; this one is the thing they open first.

Two things worth knowing before you start:

- **The booking body is bigger than round one describes.** Creation now requires
  `vehicle_class_id` and `pickup_branch_id` as well as the dates, because requirement 4
  waitlists a vehicle class and requirement 7 blacks out individual vehicles. A round-one
  shaped body answers `422`. The collection should make the full shape obvious rather than
  leaving a grader to discover it from a validation error — `docs/REQUIREMENTS-TRACE.md` has
  the reasoning under "The one divergence".
- **Seeded dates are relative to the day the seed runs.** A collection that hard-codes
  dates will drift into "start_date must not be in the past". Prefer Postman variables
  computed at request time, or say in the README that the seed must be re-run.

Ticket 49 then extends the collection to the round-two surface; this one only has to cover
what round one asked for.
