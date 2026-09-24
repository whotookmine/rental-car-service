# 23 — Vehicle class catalogue

**What to build:** A provider's catalogue of what kinds of car it rents — economy, SUV,
van and so on. This is the thing a customer books and the thing a waitlist queues for.
It exists because the second round of requirements talks about a "fully-booked vehicle
class", and until now the system modelled no vehicles at all.

**Blocked by:** None — can start immediately

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] An admin creates a vehicle class under a provider, with a name and a description
- [x] An admin edits and removes a vehicle class
- [x] A class belongs to exactly one provider and cannot be moved between providers
- [x] Any authenticated user lists a provider's vehicle classes
- [x] A registered user is refused 403 on create, edit and remove
- [x] An unauthenticated caller is refused 401
- [x] Class names are unique within a provider, and the duplicate is refused as a conflict
- [x] Removing a class that has vehicles or bookings against it is refused rather than
      cascading, so history is never destroyed by catalogue housekeeping
- [x] Classes belonging to a retired provider are still fetchable, matching how retired
      providers themselves behave

## Notes

### Surface

Created and listed under the provider, then addressed directly — the same shape bookings
already use, for the same reason: a class cannot exist without a provider, but once it
exists its own identifier is enough.

```
POST   /providers/{provider_id}/vehicle_classes   admin   201
GET    /providers/{provider_id}/vehicle_classes   any     200   ordered by name, then id
GET    /vehicle_classes/{id}                      any     200
PATCH  /vehicle_classes/{id}                      admin   200
DELETE /vehicle_classes/{id}                      admin   204
```

`PATCH` rather than `PUT` because name and description are genuinely independent, as with
providers. `DELETE` answers 204 like a booking deletion, not 200 like provider retirement:
this one really removes the row.

### Judgement calls

**A class cannot be moved between providers because no request can express it.** The
update schema simply has no `provider_id` field, and `extra="forbid"` turns an attempt
into a 422. That beats accepting the field and refusing it in the handler — there is no
code path to forget.

**Names are unique per provider, case-insensitively.** "SUV" and "suv" are the same kind
of car to a reader, so allowing both under one provider would make the catalogue lie. Two
different providers may each offer an "SUV", so the constraint is per provider. The
guarantee is a unique index on `(provider_id, lower(name))`; the handler's own lookup is
only there to produce a readable sentence in the ordinary case, with the `IntegrityError`
caught and mapped to the same 409 for the concurrent case.

Alembic's autogenerate log reports that index as covering only `provider_id` — it cannot
render the expression — but the `lower(name)` term is in the generated migration and in
the database. There is a comment in the migration saying so, because the log line looks
like a bug.

**Adding a class to a retired provider is allowed.** Retirement stops new bookings; it is
not a freeze on the record. Classes under a retired provider stay listable and fetchable,
matching how retired providers themselves behave.

**`get_vehicle_class_or_404` depends on `get_current_user`**, exactly as
`get_provider_or_404` does and for the same reason: a parameter dependency otherwise
resolves ahead of the route's own auth dependency, and an anonymous caller could read the
status code to learn which identifiers exist. Verified — `GET /vehicle_classes/999`
without a token answers 401, not 404.

### The in-use refusal, and how it was actually verified

"Removing a class that has vehicles or bookings against it is refused rather than
cascading" names two things that do not exist yet: vehicles arrive in ticket 24, and a
booking gains a class in ticket 25. The route is written now anyway, because the
alternative is a handler that answers 500 the moment the first reference appears.

The mechanism is the database, not the handler: every table that comes to reference a
vehicle class must do so `ON DELETE RESTRICT`, and the route catches the resulting
`IntegrityError` and answers 409. **Tickets 24 and 25 have to honour that**, so a line
saying so has been added to both.

This was not taken on trust. A throwaway table with an `ON DELETE RESTRICT` reference to
class 2 was created directly in the database, the delete attempted over HTTP, the table
dropped, and the delete retried:

```
DELETE /vehicle_classes/2 while referenced   -> 409 {"detail":"Vehicle class is in use and cannot be removed."}
DELETE /vehicle_classes/2 once free          -> 204
```

The second line matters as much as the first: it shows the session recovers from the
rolled-back failure rather than staying poisoned.

### Verified

Against a running app and a real PostgreSQL, every criterion above including the negative
cases. Highlights:

```
POST p1 'Economy'                                -> 201
POST p1 'SUV'                                    -> 201
POST p2 'SUV'  (other provider)                  -> 201
POST p1 'SUV' / 'suv' / '  SUV  '                -> 409 (all three)
POST as registered user                          -> 403
POST anonymous                                   -> 401
PATCH provider_id                                -> 422 extra_forbidden
PATCH name to its own current name               -> 200 (not a self-conflict)
GET  /vehicle_classes/999 anonymous              -> 401, not 404
PATCH /vehicle_classes/999 as registered user    -> 403, not 404
GET  /vehicle_classes/99999999999                -> 422, not 500
GET  retired provider's classes                  -> 200
DELETE then GET                                  -> 204 then 404
```

Migration round-trip: `upgrade` -> `downgrade base` -> `upgrade` (6 migrations), then
`alembic check` reports no drift. `GET /openapi.json` is 200 and the server log carries no
tracebacks.

### Left out

No capacity, availability or booking involvement — tickets 24, 25 and 26. No per-class
pricing; that is Garfield's ticket 33. A class carries a name and a description and
nothing else.
