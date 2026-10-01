# 47 — Seed data for the new model

**What to build:** The demo command has to show all of this working. It already creates
providers, users and bookings; it now needs branches, vehicle classes, vehicles, prices,
a blackout, a full class and a waiting queue — because most of the new features cannot be
demonstrated from an empty database.

**Blocked by:** 41, 38, 46

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] The existing seed still produces everything it did before, including the ended
      booking that makes reviews demonstrable
- [ ] Providers have several branches, with distances recorded between them
- [ ] At least one branch pair has one-way enabled and at least one does not, so both
      outcomes can be shown
- [ ] At least one branch offers delivery and one does not
- [ ] Vehicle classes have prices, and at least one class is deliberately left unpriced
- [ ] One class is seeded **full** for a known date range, so the waitlist can be joined
      immediately without first booking it out by hand
- [ ] One vehicle has a maintenance blackout over a known range
- [ ] A waitlist queue exists with more than one person in it, so FIFO order is visible
- [ ] Re-running produces the same state rather than duplicates, and it still refuses to
      run when the environment is production
- [ ] Every demo credential and every seeded identifier a demo needs is printed or
      documented

## Coordination note

Blocked on Time's 41 and 46 as well as your own 38. This is the integration point where
both halves of the round meet for the first time, so expect to find disagreements between
them here rather than earlier. Tickets 48 and 49 follow it and are also yours, so the whole
tail is one person's — nothing bounces back.


## Note from Time — what the fixture already guarantees

Patched up to the current model on 2026-10-02 after ticket 29 left it crashing. It now
covers: branches for every provider, two for the first; one inter-branch distance; one
one-way enablement **in a single direction** so the directional refusal stays demonstrable;
daily rates on all but one class, "Classic" left unpriced so an unpriceable quotation can
be shown; uneven vehicle counts so the one-car class can be filled in one request; and two
bookings of different shapes, the ended one being one-way and reviewable.

Each of those exists to make one rule demonstrable rather than to look full. Keep that
property when rebuilding it — a fixture where everything is enabled hides exactly the
refusals a demo needs to show. `docs/SPEC.md` has the table.
