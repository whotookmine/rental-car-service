# 26 — A full vehicle class refuses new bookings

**What to build:** The first real inventory rule. A class can only be booked as many times
over a given date range as it has vehicles. This is what makes "fully-booked" mean
something, and it is the precondition for the waitlist in ticket 43.

**Blocked by:** 25

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] A booking is refused as a conflict when every vehicle in the class is already taken
      for any day of the requested rental period
- [x] The refusal says the class is fully booked for those dates, not merely that something
      went wrong
- [x] Overlap is counted per day: two bookings sharing even one day both consume capacity
      that day
- [x] A class with three vehicles accepts three overlapping bookings and refuses the fourth
- [x] Capacity frees the moment a booking is deleted, exactly as a user's own slot does
- [x] The count is taken under a lock, so two simultaneous requests cannot both see the
      last vehicle and both take it — the same failure the three-active cap had, and the
      reason ADR 0001 chose PostgreSQL
- [x] "Today" and all date comparisons go through the business-timezone helper
- [x] The rule applies to admin edits as well as owner ones, measured against the class
- [x] `app/seed.py` gives its vehicle classes cars. Ticket 25 added classes to the seed
      but no vehicles, so the moment this rule lands every seeded class has capacity zero
      and refuses every booking — including the fixture's own

## Notes

### How the rule is measured

Per day, not per booking. Two bookings sharing even one day both consume a car that day,
so comparing whole periods would let a class be over-booked by bookings that merely fail
to nest. The busiest single day in the requested period is compared against the number of
cars in the class:

```sql
SELECT COALESCE(MAX(taken), 0) FROM (
    SELECT COUNT(b.id) AS taken
    FROM generate_series(:start_date, :end_date, '1 day') AS d(day)
    LEFT JOIN bookings b ON b.vehicle_class_id = :vehicle_class_id
                        AND b.start_date <= d.day AND b.end_date >= d.day
                        AND (:excluding_booking_id IS NULL OR b.id <> :excluding_booking_id)
    GROUP BY d.day
) per_day
```

`generate_series` walks the days one at a time. It is the simplest thing that is
obviously correct, and the series is bounded — a rental period is at most thirty days by
the schema rule, so this is at most thirty rows. A cleverer version would only evaluate
the days on which occupancy can change; there is no reason to pay that complexity for
thirty rows.

### The lock, and why the order matters

`SELECT ... FOR UPDATE` on the vehicle class row, taken before the count, for exactly the
reason the active-booking cap locks the owner.

**Every path that takes both locks takes the owner first and the class second.** Two
routes taking them in opposite orders is how a deadlock is built, and PostgreSQL would
resolve it by killing one caller's transaction at random. That is written into the
docstring, the router comments, and `docs/SPEC.md`, because it is the kind of constraint
that is invisible until it bites.

Proved rather than assumed, the same way the cap was — two concurrent sessions racing for
the last car in a one-vehicle class:

```
WITHOUT lock: results=['booked', 'booked']        bookings on a 1-car class: 2
WITH lock   : results=['booked', '409 refused']   bookings on a 1-car class: 1
```

The script lives in the scratch directory, not the repo; it exists to answer the question
once, and the answer is recorded here.

### Judgement calls

**The caller's own cap is checked before the class's capacity.** The three-active limit is
the one they control entirely — they can free a slot by deleting a booking of their own —
and checking it first skips the per-day query for a request that was going to fail anyway.
It is also what fixes the lock order.

**Re-dating is checked whatever the new dates are**, including ones wholly in the past.
This differs from the active-booking cap, which is only re-checked when the edit leaves
the booking active. A past-dated booking still occupied a car on those days, so an admin
correcting history must not be able to record four rentals of a class that only ever had
three cars.

**Selling cars can leave a class over its capacity.** Nothing stops an admin deleting a
vehicle while bookings stand against its class. Those bookings survive — history is never
destroyed to satisfy a later rule — and only new bookings are refused. Deleting the
*class* is still refused outright by the `RESTRICT` key from ticket 23.

**The refusal names the class and the dates**, and reads differently for a class with no
cars at all, with one, or with several. "This class has no vehicles" is a different
problem from "all 3 of its vehicles are taken" and the caller can act on each differently.

### The seed now has cars

Ticket 25 added vehicle classes to the fixture but no vehicles, which this rule would have
turned into a seed where every class refuses every booking — including the fixture's own.
Each class now has cars: Economy 3, SUV 1, Van 2, Classic 1. The counts differ on purpose,
so a demo can fill the one-car class and watch the refusal without making three bookings
first.

### Verified

Against a running app and a real PostgreSQL. Capacity 1 (SUV), showing the per-day
boundary exactly:

```
u1 books day 10-15                  -> 201
u2 books day 10-15                  -> 409 fully booked
u2 books day 15-20 (shares day 15)  -> 409 fully booked
u2 books day 16-20 (adjacent)       -> 201
u3 books day  9-9  (before)         -> 201
u3 books day  9-10 (shares day 10)  -> 409 fully booked
```

Capacity 3 (Economy):

```
three overlapping bookings          -> 201, 201, 201
the fourth                          -> 409 "All 3 of its vehicles are taken..."
a single day inside the window      -> 409
a period after the window           -> 201
delete one of the three             -> 204
the fourth, retried                 -> 201  (capacity freed immediately)
```

Re-dating and admin edits:

```
re-date into the full window        -> 409
re-date somewhere free              -> 200
re-date to its own current dates    -> 200  (the booking is excluded from its own count)
admin re-dates someone else's into the full window -> 409
admin re-dates it somewhere free    -> 200
```

Empty class:

```
book a class with no vehicles       -> 409 "This class has no vehicles."
```

Round-one and ticket-25 rules re-checked unchanged: admin creating a booking 403, retired
provider 409, over-thirty-days 422, another provider's class 409. No new `date.today()`
anywhere outside `app/core/clock.py`. `alembic check` reports no drift — this ticket adds
no schema. `GET /openapi.json` is 200; no tracebacks in the log.

### Left out

No availability query — a caller still discovers that a class is full by being refused.
That is ticket 27, which is next. No waitlist (43), no blackout windows (39); a car under
maintenance still counts towards capacity until ticket 39 says otherwise.
