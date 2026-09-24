# 25 — Bookings name a vehicle class

**What to build:** A booking stops being "a period with a provider" and becomes "a period
with a provider, for a kind of car". Every existing booking rule keeps working; the
booking simply carries more. This is the change that makes capacity, blackouts and the
waitlist expressible at all.

**Blocked by:** 24

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] Creating a booking requires a vehicle class, and the class must belong to the
      provider in the path
- [x] A class from a different provider is refused
- [x] A booking that names no class, or a class that does not exist, is refused
- [x] The class appears on every booking response, alongside the provider
- [x] The class is fixed at creation and cannot be changed by re-dating, for the same
      reason the provider cannot: a review must keep describing what was actually rented
- [x] Every rule from tickets 08 to 20 still holds unchanged: date shape, the thirty-day
      maximum, no past-dated creation, the three-active cap, ownership scoping, admin
      oversight, and the reviewed-booking rule
- [x] Existing bookings are migrated rather than destroyed; the migration states what
      class historical rows are given and why
- [x] The booking's foreign key to the vehicle class is `ON DELETE RESTRICT`, matching
      ticket 23: removing a class that bookings point at must answer 409, never cascade

## Hand-off note — NOW UNBLOCKED, tell Garfield

**Merged. Garfield's tickets 29 and 33 are no longer blocked.** A booking carries
`vehicle_class_id`, and `BookingRead` nests the class as `vehicle_class`.

**This ticket was the only thing Garfield waits on until integration.** His tickets 29
(pickup branch on a booking) and 33 (money) both need a booking that names a vehicle class.
He can do 28, 30, 31 and 36 without it, so there is roughly four tickets of slack — but
tell him the moment this merges rather than at the end of the phase.

It also opens the shared file. From here, `app/bookings/` is edited by both of us: Time in
25, 26 and 41, Garfield in 29, 32 and 37. Each of those adds a column and a rule to the
same model and router. Land them one at a time and pull before starting, or the merges get
ugly.

## Notes

### What changed

`bookings.vehicle_class_id`, required, `ON DELETE RESTRICT`. `BookingCreate` takes it;
`BookingUpdate` deliberately does not. `BookingRead` nests it as `vehicle_class`.

### The two refusals are different mistakes

- **A class that does not exist -> 422.** It is a bad value in the request body, not a
  missing resource at the path being addressed. The provider in the path was found. This
  matches what ticket 24 settled for editing a vehicle.
- **A class belonging to another provider -> 409.** Well-formed request, wrong state. The
  message names both — *"Vehicle class 'Economy' does not belong to provider 'Fast
  Wheels'"* — because with per-provider catalogues the caller can be looking at two
  classes with the same name and needs to know which half of the request to change.

The class is resolved **before** the active-booking cap is taken. Otherwise a user at the
cap who also named the wrong class would be told about the cap, fix nothing useful, and
hit the class error next.

### Nesting a summary, not the full read shape

`BookingRead` nests `VehicleClassSummary`, which has no `vehicle_count`. The count comes
from an aggregate query, not from the model, so validating the full `VehicleClassRead`
straight from a `VehicleClass` object would fall back to the default and report a
confident zero on every booking.

**This is not hypothetical — the nested provider already does exactly that.** See below.

### A defect found while verifying: ticket 50

`average_rating` and `review_count` are right when a provider is fetched directly and
always `null`/`0` when the same provider is nested inside a booking, for precisely the
reason above. Reproduced after leaving a review on the seeded ended booking:

```
GET /providers/1   -> "average_rating": 4.0,  "review_count": 1
GET /bookings/1    -> "provider": { ... "average_rating": null, "review_count": 0 }
```

Pre-existing, from round one, and not caused by this ticket. **Not fixed here** — changing
the shape of the nested provider is a separate behaviour change deserving its own commit
and its own verification. Raised as **ticket 50** and recorded in `docs/SPEC.md`, which now
says what a nested block does and does not carry.

### The migration, and what historical bookings were given

Added nullable, backfilled, then set `NOT NULL`. Adding it `NOT NULL` outright would fail
on any database that already holds bookings — which is every developer's, and would be the
graders' too.

Nothing in the data says what was actually rented: the catalogue did not exist when those
bookings were made. Picking each provider's first or cheapest class would put a fact in the
record that nobody ever asserted, and a review attached to that booking would then describe
a kind of car the renter may never have had. So every provider that has bookings gets one
class named **"Unclassified"**, described as what it is, and its bookings point at that. It
reads as an absence rather than as a guess.

The downgrade drops the column but **deliberately leaves those classes behind**: an admin
may since have renamed one, described it, or put cars in it, and there is no way to tell
those apart from the ones the migration made. Dropping a column is reversible; deleting
someone's catalogue is not.

Verified on a database that really held a legacy booking, not on an empty one:

```
before: booking 1, provider 1, no class
after : booking 1 -> class 4 "Unclassified" (provider 1), row intact
downgrade -1 -> booking still there; upgrade again -> reuses class 4, no duplicate
```

### The seed had to be fixed too

`app/seed.py` creates bookings directly through the ORM, so it broke the moment the column
became required. It now creates one vehicle class per provider — two for the first, so a
demo has a choice — and the wipe deletes bookings, then vehicles, then classes, then
providers, since two `RESTRICT` foreign keys now stand in the way.

It creates **no vehicles**. Capacity is not enforced until ticket 26, and ticket 47
rebuilds this fixture properly. **Ticket 26 must give the seeded classes cars**, or every
seeded class will have capacity zero and refuse every booking the moment that rule lands.

### Verified

Against a running app and a real PostgreSQL:

```
POST with a valid class                       -> 201, class echoed in the response
POST with no vehicle_class_id                 -> 422 Field required
POST vehicle_class_id null / 0 / 99999999999  -> 422 (type, ge, le) — never 500
POST class 999                                -> 422 Vehicle class not found.
POST another provider's class                 -> 409 naming both
PUT sending vehicle_class_id                  -> 422 extra_forbidden
PUT dates only                                -> 200, class unchanged
```

Every rule from tickets 08 to 20, re-run unchanged:

```
end before start / past start / over 30 days  -> 422 each
booking a retired provider                    -> 409
2nd and 3rd active -> 201, 201; 4th           -> 409 "You already hold 3..."
admin creating a booking                      -> 403 Admins do not hold bookings.
another user's booking, fetch and delete      -> 404 both
admin fetch / admin list                      -> 200, all 5 bookings carry a class
review an ended booking                       -> 201, provider average becomes 4.0
re-date that reviewed booking forward         -> 409 reviewed-booking refusal
```

And the new `RESTRICT`, with real bookings rather than the throwaway table ticket 23 used:

```
DELETE a class that bookings point at         -> 409
DELETE an unused class                        -> 204
```

Migration round-trip: `upgrade` -> `downgrade base` -> `upgrade` (8 migrations), then
`alembic check` reports no drift. `GET /openapi.json` is 200; no tracebacks in the log.

### Left out

Capacity is still not enforced — a class with no cars at all takes bookings happily. That
is ticket 26. No availability query, no waitlist, no blackout interaction.
