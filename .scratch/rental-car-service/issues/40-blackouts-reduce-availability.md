# 40 — Blacked-out vehicles leave availability

**What to build:** A vehicle in the workshop is not a vehicle you can rent. Availability
must count only vehicles that are actually on the road for the whole requested range.

**Blocked by:** 39, 27

**Owner:** Time

**Status:** done — verified against a running app and a real database, with one criterion deliberately left open (see Notes)

- [x] Availability excludes any vehicle whose blackout window overlaps even one day of the
      requested range
- [x] A class of three vehicles with one blacked out reports two available
- [x] A class with every vehicle blacked out reports zero, not an error and not an omission
- [x] A window that ends the day before the range starts does not reduce availability, and
      one that starts the day the range ends does — state the boundary explicitly
- [x] Cancelling a window restores availability immediately
- [ ] Availability and booking still agree: whatever availability reports, booking behaves
      the same way — **NOT met, and cannot be met by this ticket. See Notes.**

## Notes

### What changed

One CTE in the availability query. `class_capacity` no longer counts a vehicle that has a
blackout window overlapping the requested range, so `free_count` means "unbooked **and** on
the road" rather than "unbooked".

No migration, no new route, no schema change. The whole ticket is four lines of SQL and the
reasoning about where they go.

### The line that matters is *where* the test goes, not what it says

The blackout test is in the `LEFT JOIN` condition, **not** in a `WHERE` clause:

```sql
LEFT JOIN vehicles v ON v.vehicle_class_id = vc.id
    AND NOT EXISTS (SELECT 1 FROM blackout_windows bw
                    WHERE bw.vehicle_id = v.id
                      AND bw.start_date <= :end_date
                      AND bw.end_date   >= :start_date)
```

In a `WHERE` clause it would have discarded the class's own row along with its last
remaining car, so a class whose every vehicle is in the workshop would have **vanished from
the response** instead of reporting zero. That is exactly the "full versus does not exist"
distinction this endpoint was built for in ticket 27, and it would have been a silent
regression of it — the response would still have been a valid 200 with a plausible list.
Verified explicitly: all three Economy cars blacked out gives `Economy=0`, and the class is
still present.

### The boundary, stated

Inclusive on both sides, matching every other period in this system. All three cases run:

```
window ENDS the day before the range starts   -> 3 free  (no effect)
window STARTS the day the range ends          -> 2 free  (reduces)
window STARTS the day after the range ends    -> 3 free  (no effect)
```

A window overlapping a **single** day of the range removes the car for the whole range,
because a car you must return mid-rental is not a car you can rent for that rental.

### The criterion I did not tick, and why

> *Availability and booking still agree: whatever availability reports, booking behaves the
> same way*

**This cannot be satisfied by this ticket**, because making booking behave the same way *is*
ticket 41 in its entirety — "a booking is refused as a conflict when the class has no vehicle
free of blackouts". Implementing it here would be absorbing the next ticket, which the scope
rule in `CLAUDE.md` forbids; ticking it on the strength of the half that does hold would be
reporting a criterion as met on behaviour I had watched not happen.

So it is measured rather than asserted. They **do** agree on bookings-versus-capacity, which
is the ticket 27 guarantee and is preserved:

```
SUV, one car, free over the range   -> free_count 1
book it                             -> 201
                                    -> free_count 0
book it again                       -> 409 "Vehicle class 'SUV' is fully booked..."
agreement: availability 0 and booking refused -> True
```

They do **not** agree on blackouts:

```
every Economy car blacked out over 2026-12-26..2026-12-27
  availability says  -> free_count 0
  booking says       -> 201
```

Recorded in `docs/SPEC.md` under both the availability rules and the maintenance rules, with
that transcript, so the next reader finds the gap described rather than discovering it. **Do
ticket 41 next**: a reported zero that still takes bookings is the kind of inconsistency a
grader finds in a minute.

### What was deliberately left alone

- **`vehicle_count` on a vehicle class still counts every car**, blacked out or not. It is
  the size of the fleet, not availability for a range, and no range is given when a class is
  fetched. Changing it would make a class's own count disagree with itself depending on who
  asked.
- **A booking already standing over a window is untouched.** Nothing here refuses, so
  nothing here needs to decide what happens to existing bookings — that decision is
  ticket 41's, which asks for it explicitly.

### Verified

Against a running app and a real PostgreSQL, every assertion checked programmatically rather
than read off the screen:

```
baseline, three Economy cars, no windows        -> 3
one of three blacked out over the range         -> 2
window covering only the final day of the range -> 2
window ending the day before the range          -> 3
window starting on the range's last day         -> 2
window starting the day after the range         -> 3
all three blacked out                           -> 0, class still listed
cancel one window                               -> 1
cancel the rest                                 -> 3
one booked                                      -> 2
one booked and one blacked out                  -> 1
one booked and two blacked out                  -> 0
a range nowhere near the windows                -> 3
other classes in the same response              unaffected (SUV stays 1 throughout)
```

`alembic check` reports no drift (no migration was needed). The seed runs. `app/smoke.py`
gained seven availability checks, including that the count drops by **exactly** one and is
restored by cancelling — compared against the count measured moments before rather than a
hardcoded number, so ticket 47 rebuilding the fixture cannot quietly invalidate them.
**111/111 passed, twice with no re-seed between.**
