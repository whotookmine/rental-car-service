# 41 — Bookings overlapping a blackout are refused

**What to build:** The enforcement half of maintenance. Availability reporting a vehicle as
gone is not enough; a booking that would consume it has to be refused, including when the
window is scheduled after the booking was made.

**Blocked by:** 40, 26

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] A booking is refused as a conflict when the class has no vehicle free of blackouts
      for the whole rental period
- [x] The refusal distinguishes "fully booked" from "unavailable for maintenance", so the
      user knows whether waiting will help
- [x] Re-dating a booking onto days where the class is blacked out is refused too, for
      owner and admin alike
- [x] Capacity counts vehicles, blackouts and existing bookings together: two vehicles, one
      blacked out, one already booked means the class is full
- [x] Decide and state what happens to a booking that already exists when an admin
      schedules a blackout over it — refused, allowed, or allowed with the booking flagged.
      Whichever is chosen, an existing booking must not silently vanish
- [x] The check runs under the same lock as the capacity count, so a blackout and a booking
      cannot race

## Hand-off note — HALF DONE, tell Garfield

**Blackout enforcement is in.** Of the two things his ticket 47 waits on, this is the one
that is now finished. The other is **ticket 46** — the waitlist chain, 42 through 46, none of
which has started. So 47 is still blocked, but only on the waitlist now.

When he does get to 47, the fixture needs a blacked-out vehicle. Two things to know:

- **`_WIPE_ORDER` in `app/seed.py` must list `blackout_windows`** before `vehicles`, which it
  now does. Any further table referencing an existing one with `RESTRICT` needs the same.
- **A seeded window will change what the seeded classes can take.** Blacking out one of the
  three Economy cars makes that class refuse a third concurrent booking, so whichever
  demo walkthrough ticket 48 writes has to account for it. Better to black out a car in a
  class the walkthrough does not book.

## Notes

### What changed

`ensure_class_has_room` in `app/bookings/rules.py` now counts three things in one
comparison instead of two:

```
available = vehicles in the class − vehicles off the road for any day of the period
refused when the busiest day already has `available` bookings on it
```

Nothing else moved. The update route already called the same function, so re-dating
inherited the rule without a line of its own — which is why the owner-and-admin criterion
was satisfied by construction rather than by two more code paths.

### The two counts had to agree by construction, not by coincidence

This is the same arithmetic `GET /providers/{id}/availability` performs, deliberately. Ticket
40 left a gap where availability reported zero and booking answered 201; closing it by
copying the rule in a second shape would have left the two free to drift apart again at the
next ticket. Measured in both directions:

```
SUV over its own blackout                 free=0  booking=409   agree
Economy, 2 of 3 blacked out + 1 booked    free=0  booking=409   agree
Economy on a clear range                  free=3  booking=201   agree
```

Ticket 40's last criterion, left unticked on purpose, is now ticked there with a note.

### The refusal distinguishes four situations, not two

The criterion asked for "fully booked" versus maintenance. There are actually four, and the
remedy differs in each, so the message differs in each:

```
no vehicles at all   -> "it has no vehicles."
all in the workshop  -> "its only vehicle is off the road for maintenance for part of that
                        period. Waiting will not free one, because no other booking is
                        holding them; try different dates."
fully booked         -> "Its only vehicle is taken on at least one of those days."
both                 -> "2 of its 3 vehicles are off the road for maintenance for part of
                        that period, and the 1 still on the road are taken on at least one
                        of those days."
```

The distinction a caller actually needs is **whether waiting helps**. A fully-booked class
frees up when someone cancels, which is exactly what the waitlist in ticket 43 will queue
for. A class in the workshop will not, however long anyone waits — the cars are not in
another renter's hands. The mixed message names both counts so the caller knows part of the
shortfall is never coming back to them.

**The word "unavailable" is not used**, even though the ticket's own criterion uses it.
`CONTEXT.md` forbids it under **Fully Booked**, and the reason is exactly this ticket: if
both situations can be called "unavailable" then the message that was supposed to tell them
apart stops doing so. "Off the road for maintenance" is used instead.

The pure fully-booked wording from ticket 26 is **unchanged**. A caller who has learnt what
that sentence means should not find it reworded because a feature they never touched landed.

### A booking that already exists when a blackout is scheduled over it

The ticket asked for a decision between refusing, allowing, and allowing-with-a-flag.

**Allowed. The booking stands. Nothing is flagged.**

- **Refusing the window** would mean the database cannot record a car that has broken down —
  which is the single thing maintenance scheduling exists for. Reality does not ask
  permission, and a system that refuses to record it starts lying about the workshop.
- **Flagging the booking** would add a field that nothing reads and no rule acts on. An
  indicator nobody consumes is worse than none: it looks like a guarantee.

So the window is written, the booking is untouched, and the class is simply over-committed
for those days. Availability reports the lower number immediately and new bookings are
refused. Verified that the standing booking survives and is still fetchable:

```
booking 22 created for 2027-02-09..2027-02-10
blackout scheduled over it   -> 201 allowed
the booking is still there   -> 200, dates unchanged
availability now reports     -> 1
```

**The cost is accepted knowingly:** nothing stops an admin doing this by accident, and the
only way back is to talk to the renter and delete the booking — which is what would happen
in the world anyway. `docs/SPEC.md` states both the choice and the cost.

### The shared lock, which needed a change to ticket 39's code

Ticket 39 locked the **vehicle** row when scheduling a window. Booking locks the **vehicle
class** row. Those are different rows, so the two could not see each other: a booking could
read "one car free, none in the workshop", and a concurrent window could make that false
before the booking inserted.

A booking cannot lock the vehicle instead — it names a class, not a car, and has no way to
know which vehicle to lock. So scheduling a window now takes the class lock too, **before**
the vehicle lock, matching the order already written down in ticket 39: owner, then vehicle
class, then vehicle.

Proved by holding the class row from outside the application and timing both requests:

```
## while the vehicle class row is held by another transaction
  POST a booking                   [201] waited  4.6s  <- BLOCKED on the lock
  POST a blackout window           [201] waited  4.6s  <- BLOCKED on the lock

## with nothing holding the row, for comparison
  POST a booking                   [201] waited  0.0s  <- did not contend
  POST a blackout window           [201] waited  0.0s  <- did not contend
```

That is the evidence, and it is worth being precise about what it shows: the two paths
serialise on the same row. It is not a reproduction of the corruption itself, which cannot
be observed from outside the API — a booking accepted on a stale read looks identical to one
accepted on a fresh read.

### Verified

Against a running app and a real PostgreSQL, every expectation asserted in code:

```
one-car class, car blacked out, book it         -> 409 naming maintenance
same, message distinguishes from fully booked   -> 409 "fully booked", no mention of maintenance
3 cars, 2 blacked out, 1 booked, book again     -> 409 naming both counts
availability vs booking, three scenarios        -> agree in all three
blackout over a standing booking                -> 201, booking intact, availability drops
owner re-dates onto blacked-out days            -> 409
admin re-dates onto the same days               -> 409
owner re-dates onto clear days                  -> 200
window ends the day before the period           -> 201 allowed
window starts on the period's final day         -> 409 refused
cancel that window, book again                  -> 201
```

Each throwaway booking used its own registered user, because the first run of the script hit
the three-active cap and reported a failure that was the test's fault, not the code's.

`alembic check` reports no drift (no migration needed). The seed runs. `app/smoke.py` gained
a nine-check enforcement section on a class of its own: **124/124 passed, twice with no
re-seed between.**

### Requirement 7 is now complete

All three clauses of the second-round requirement — schedule per vehicle, exclude from
availability, prevent overlapping bookings — are built and verified. Recorded in
`docs/REQUIREMENTS-TRACE.md`.

### Left out

No waitlist interaction: a user refused because every car is in the workshop cannot queue for
one, and the message tells them to try different dates rather than offering to wait. That is
tickets 43 to 46. No notification to anyone holding a booking over a newly scheduled window —
ticket 42 builds notification records, and this would be a natural first user of them.
