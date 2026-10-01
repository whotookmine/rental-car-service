# 29 — Bookings name a pickup branch

**What to build:** A booking records where the car is collected. Until a booking has a
pickup branch there is nothing for a drop-off branch to differ from, so this precedes
one-way rentals.

**Blocked by:** 28, 25

**Owner:** Garfield

**Status:** done — verified against a running app and a real database

- [x] Creating a booking requires a pickup branch, and it must belong to the provider in
      the path
- [x] A branch belonging to a different provider is refused
- [x] The pickup branch appears on every booking response
- [x] The pickup branch is fixed at creation, like the provider and the vehicle class
- [x] Every existing booking rule still holds, including capacity from ticket 26
- [x] Existing bookings are migrated to their provider's first branch, and the migration
      says so

## Notes

Added `pickup_branch_id` (FK to `branches`, ON DELETE RESTRICT) to `Booking` model and
`BookingCreate` schema. `BookingRead` nests `pickup_branch` as a `BranchRead`.

`BookingUpdate` has no `pickup_branch_id` and `extra="forbid"`, so sending it on re-date
answers 422 — same protection as `vehicle_class_id`.

New rule `resolve_branch_for_provider` in `app/bookings/rules.py` mirrors
`resolve_vehicle_class_for_provider`: nonexistent branch → 422, wrong provider → 409.

Migration `c5f625e54f25`: adds column nullable, backfills each existing booking to its
provider's lowest-id branch (the "Main Branch" seeded by cb0b6c819227), then sets NOT
NULL. The ON DELETE RESTRICT FK makes the branch-in-use guard in ticket 28's delete
handler real.

## Coordination note

Blocked on Time's ticket 25, which adds the vehicle class to a booking. You can do 28, 30,
31 and 36 first without waiting.

This is also where you start editing `app/bookings/`, which Time is editing in 25, 26 and
41. Pull before you start and land your booking-touching tickets (29, 32, 37) one at a
time.


## Follow-up from Time — the seed was left broken

Making `pickup_branch_id` NOT NULL broke `app/seed.py`, which writes bookings through the
ORM rather than the API. `uv run python -m app.seed` — a command the README documents —
died with:

```
sqlalchemy.exc.IntegrityError: null value in column "pickup_branch_id"
of relation "bookings" violates not-null constraint
```

Found on 2026-10-02 while checking the pull. Fixed in a separate commit rather than here:
the fixture now creates branches for every provider, a distance and a one-way enablement
for the first provider's pair, and gives both seeded bookings a pickup branch. No change
to this ticket's own behaviour, which was correct.

This is the second time a required booking column has killed the fixture — ticket 25 was
the first — so `CLAUDE.md` now says to run the seed before closing any ticket that touches
a model.
