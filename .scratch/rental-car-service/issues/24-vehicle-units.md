# 24 — Vehicle units

**What to build:** The individual cars a provider actually owns, each belonging to one
vehicle class. Capacity is a count of these, and maintenance blackouts in ticket 39 are
scheduled against one of them, so both later features need units rather than just classes.

**Blocked by:** 23

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] An admin adds a vehicle to a class, with a registration or plate identifier
- [x] An admin edits and removes a vehicle
- [x] The plate identifier is unique across the system and the duplicate is a conflict
- [x] A vehicle belongs to exactly one class and cannot be moved to another provider's class
- [x] Any authenticated user can see how many vehicles a class has, without necessarily
      seeing each plate
- [x] A registered user is refused 403 on every write
- [x] Removing a vehicle that has a blackout window or is otherwise referenced is refused
      rather than cascading
- [x] Adding vehicles raises that class's capacity, which ticket 26 then enforces
- [x] The vehicle's foreign key to its class is `ON DELETE RESTRICT`, so ticket 23's
      "vehicle class is in use" refusal becomes real rather than theoretical; verify that
      removing a class that has vehicles answers 409

## Notes

### Surface

```
POST   /vehicle_classes/{id}/vehicles   admin   201
GET    /vehicle_classes/{id}/vehicles   admin   200   ordered by plate, then id
GET    /vehicles/{id}                   admin   200
PATCH  /vehicles/{id}                   admin   200
DELETE /vehicles/{id}                   admin   204
```

### The count is public; the plates are not

"Any authenticated user can see how many vehicles a class has, without necessarily seeing
each plate" is the criterion that shaped this ticket. It is answered by splitting the two:

- `vehicle_count` appears on **`VehicleClassRead`**, so every existing vehicle class
  response — the list under a provider, and the single fetch — now carries it, readable by
  any authenticated user.
- **Every route in this package is admin-only, reads included.** That makes these the only
  privileged reads in the service. It is deliberate: a plate identifies a car on the road
  and is of no use to someone booking a *kind* of car, so there is nothing a renter loses.

`vehicle_count` is computed on read by aggregation, never stored — the same treatment a
provider's `average_rating` gets, and for the same reason: a stored count drifts the moment
a car is added or removed outside the one code path that maintains it. That is also what
makes "adding vehicles raises that class's capacity" true by construction rather than by
remembering to increment something. Verified by watching the count move as cars were
added, moved between classes, and deleted.

### Judgement calls

**Reclassification within a provider is allowed; moving to another provider is not.** The
criterion says a vehicle "cannot be moved to another provider's class", which is narrower
than "cannot be moved" — and rightly so, since a car genuinely does move from Economy to
Compact. So `VehicleUpdate` carries `vehicle_class_id`, unlike `VehicleClassUpdate` which
deliberately carries no `provider_id`, and the cross-provider case is refused with 409.

**A `PATCH` naming a class that does not exist answers 422, not 404.** The vehicle in the
path was found; the missing thing is a value in the body. Answering 404 would say the
addressed resource is absent, which is untrue.

**Plates are unique system-wide rather than per provider.** A plate identifies a car on
the road, so the same one under two providers means one of them is wrong. Compared without
regard to case, guaranteed by a unique index on `lower(plate)`, with the handler's own
lookup there only for a readable message and the `IntegrityError` caught for the
concurrent case. As with the vehicle class index, Alembic's log cannot render the
expression — it reports this index as covering no columns at all — and the migration
carries a comment saying to check the database, not the log.

### Ticket 23's refusal is no longer theoretical

`vehicles.vehicle_class_id` is `ON DELETE RESTRICT`, which was the criterion added to this
ticket when 23 shipped. Verified with real cars rather than the throwaway table 23 had to
use:

```
DELETE class SUV, which has 1 car    -> 409 Vehicle class is in use and cannot be removed.
DELETE that car                      -> 204
GET the class                        -> vehicle_count 0
DELETE the now-empty class           -> 204
DELETE class Economy, 2 cars         -> 409
```

A vehicle's own in-use refusal has nothing pointing at it yet — blackout windows arrive in
ticket 39 — so it was proved the same way 23's was, with a throwaway `ON DELETE RESTRICT`
table: 409 while referenced, 204 once the reference was dropped. **Ticket 39 has gained a
criterion** requiring its blackout window's foreign key to a vehicle to be `ON DELETE
RESTRICT`.

### Verified

Against a running app and a real PostgreSQL, every criterion including the negative cases:

```
POST three cars across two classes                 -> 201 x3
POST duplicate plate / lowercase / space-padded    -> 409 (all three)
GET provider's classes as a registered user        -> 200, vehicle_count 2 and 1
GET the fleet as a registered user                 -> 403
GET the fleet anonymously                          -> 401
PATCH into a sibling class, same provider          -> 200, counts move 2/1 -> 3/0
PATCH into another provider's class                -> 409
PATCH naming class 999                             -> 422
PATCH plate to its own current plate               -> 200 (not a self-conflict)
POST / PATCH / DELETE as a registered user         -> 403
GET /vehicles/999 anonymous / registered / admin   -> 401 / 403 / 404
GET /vehicles/99999999999                          -> 422, not 500
```

Migration round-trip: `upgrade` -> `downgrade base` -> `upgrade` (7 migrations), then
`alembic check` reports no drift. Round-one regression checked too — `GET /providers`,
`POST /providers/{id}/bookings`, `GET /bookings` and `/health` all still answer as before,
and the server log carries no tracebacks.

### Left out

Nothing enforces capacity yet: a class with one car will still take a hundred bookings.
That is ticket 26, which is why this ticket only has to make the number visible and
correct. No blackout windows (39), no pricing (Garfield's 33), no vehicle attributes
beyond the plate — no colour, model, year or mileage, none of which any requirement asks
for.
