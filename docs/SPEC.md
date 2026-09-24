# Rental Car Service — Agreed Design

Terminology is defined in [CONTEXT.md](../CONTEXT.md). Decisions with lasting
consequences are recorded in [docs/adr](./adr). This file is the working specification:
the rules, the surface, and the shape of the system as agreed.

## Stack

Python, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, PostgreSQL. Feature-first layout
(`auth/`, `bookings/`, `providers/`, `reviews/`, `vehicle_classes/`, `vehicles/`), with a
single `app/db/base.py` that imports every model so Alembic autogeneration sees all
tables. JSON is snake_case, bare
resources, FastAPI's default `{"detail": ...}` error shape with self-explaining messages.

## Entities

There was no Car entity in the first round of work: a booking reserved a period with a
provider and nothing else. The second round introduces the **vehicle class** — the kind
of car a provider rents — because a waitlist has to queue for something more specific
than a whole business. Since ticket 25 a booking names one.

- **User** — name, telephone, email (unique, lowercased), password hash, role
  (`user` | `admin`, defaults to `user`, never settable through the API).
- **Provider** — name, address, telephone, `is_retired`.
- **Vehicle Class** — provider, name, description. The kind of car, not an individual
  car. Belongs to exactly one provider for its whole life.
- **Vehicle** — vehicle class, plate (unique system-wide). One individual car.
- **Booking** — user, provider, vehicle class, `start_date`, `end_date` (both `DATE`).
- **Review** — booking (unique), rating 1–5, comment.

## Dates

Dates are `DATE` columns with no time
 component. "Today" is computed in the configured
business timezone (`BUSINESS_TIMEZONE`, `Asia/Bangkok`) via a single `today()` helper.
No rule may call `date.today()` directly.

## Rules

### Bookings

- `end_date >= start_date`.
- Rental period is at most 30 days.
- `start_date` must not be in the past **on creation**. Updates may touch past dates, so
  that a booking already underway can be extended and an admin can correct history.
- A registered user may hold at most 3 **active** bookings (rental period not yet ended).
  Deleting a booking frees a slot immediately. The check locks the owner's row before
  counting, so two simultaneous requests cannot both see a free slot and both take it —
  this is the transaction ADR 0001 cited when choosing PostgreSQL.
- A booking names one of that provider's vehicle classes, required at creation. A class
  that does not exist answers 422 — it is a bad value in the body, not a missing resource
  at the path — and a class belonging to a different provider answers 409, naming both so
  the caller knows which half of the request to change. The class is resolved before the
  active-booking cap is taken, so a request with the wrong class is told what is actually
  wrong with it.
- The vehicle class is fixed at creation, exactly as the provider is, and for the same
  reason: a review must keep describing what was actually rented. Sending either when
  re-dating is refused with 422, never ignored.
- A booking cannot be created against a retired provider (409). Existing bookings made
  before retirement are unaffected and remain viewable. Reinstating the provider makes it
  bookable again.
- Overlapping bookings by the same user are allowed. The active cap bounds abuse, and a
  class's capacity bounds the rest: a user may hold two bookings at once so long as the
  class has room for both.
- **A vehicle class is booked at most as many times on any one day as it has vehicles.**
  The check is per day, not per booking: two bookings sharing even one day both consume a
  car that day, so a whole-period comparison would let a class be over-booked by bookings
  that merely fail to nest. The busiest day in the requested period is compared against
  the count of cars in the class, and a peak at or above capacity is refused with 409
  naming the class and the dates. Adjacent periods do not conflict — a booking ending on
  the 10th and one starting on the 11th share no day.
- A class with no vehicles refuses every booking, and says so rather than reporting a
  generic conflict.
- The capacity check applies to re-dating as well as creation, for owners and admins
  alike, measured against the booking's own class and excluding the booking itself, which
  is moving rather than being added. Unlike the active-booking cap it is checked whatever
  the new dates are, including ones wholly in the past: a past-dated booking still
  occupied a car on those days, and an admin correcting history must not be able to record
  four rentals of a class that only ever had three cars.
- Capacity frees the moment a booking is deleted, exactly as a user's own slot does.
- Selling cars can leave a class holding more bookings than it has capacity for. Those
  bookings stand — history is never destroyed to satisfy a later rule — and only new ones
  are refused.
- The count is taken under a row lock on the vehicle class, for the reason the active cap
  locks the owner: counting and then inserting is a race, and two requests could otherwise
  both see the last car free and both take it. **Every path that takes both locks takes
  the owner first and the class second.** Two routes taking them in opposite orders is how
  a deadlock is built.
- The caller's own cap is checked before the class's capacity. It is the limit they
  control entirely, and checking it first skips the per-day query for a request that would
  fail regardless.
- Only the dates are mutable, for owner and admin alike. The provider is fixed at
  creation.
- Every edit is validated identically whether the owner or an admin makes it: date
  ordering, the 30-day maximum, and the 3-active cap, the last measured against the
  booking's owner. Admins have wider scope, not weaker rules, and share the same code
  path. The accepted cost is that an admin cannot extend an ended booking for a user who
  already holds 3 active ones, even to correct a genuine error.
- The cap is re-checked on an edit **only when the new dates would leave the booking
  active**, and the booking being edited is excluded from its own count. An owner at the
  cap can therefore still re-date their bookings, and can still edit an ended booking that
  stays ended, since it occupies no slot; what they cannot do is extend an ended booking
  into the future to gain a fourth active one.
- The refusal names whoever is actually at the limit: an owner is addressed directly, and
  an admin editing someone else's booking is told about that booking's owner.
- A booking that has a review cannot be edited such that its rental period would no
  longer be ended (409). This applies to owners and admins alike; it keeps every review
  in the table attached to a finished rental. "No longer ended" uses the same boundary as
  the active-booking cap, so moving a reviewed booking to end **today** is refused just as
  moving it into the future is.
- When an edit breaks both this rule and the cap, the review refusal is the one reported.
  It is absolute — no amount of freeing slots makes a reviewed booking movable into the
  future — whereas the cap clears on its own as rental periods end. Malformed dates still
  answer 422 ahead of either, since validation runs before the handler.
- Admins do not hold bookings. `POST /providers/{id}/bookings` refuses an admin caller
  with 403. The cap is a rule about a renter's behaviour and admin oversight is defined as
  acting on other people's bookings; an admin holding their own would make both ambiguous.

### Reviews

- One review per booking, enforced by a unique constraint.
- Creatable only once the booking's rental period has ended, and only by the booking's
  owner.
- Rating and comment are mutable by the owner; the booking it belongs to is not.
- Deleting a booking cascades to its review at the database level. Deleting a review
  leaves the booking intact and reviewable again.
- A retired provider is still reviewable by users who booked it.

### Providers

- `GET /providers` excludes retired providers and carries `average_rating` and
  `review_count` for each. An admin may pass `include_retired=true` to see retired
  providers as well; the same parameter from a registered user is ignored, so retired
  providers never reach them.
- `POST /providers/{id}/reinstate` returns a retired provider to the catalogue. Retirement
  is reversible, per ADR 0004.
- `average_rating` is computed on read by aggregation, never stored. A provider with no
  reviews returns `null`, not `0`. Rounded to one decimal place in responses, stored at
  full precision.
- `GET /providers/{id}` returns retired providers too, so users can see who they booked.
- `DELETE /providers/{id}` retires; it never removes the row.

### Vehicle classes

- A class belongs to exactly one provider and never moves. The provider is set at
  creation from the path, and the update shape carries no field for it, so there is no
  request that could express a move.
- Names are unique within a provider and compared without regard to case: "SUV" and
  "suv" are the same kind of car to a reader. Two different providers may each offer an
  "SUV". A duplicate is refused with 409. A unique index on `(provider_id, lower(name))`
  is what guarantees it; the handler's own lookup exists only to produce a readable
  message in the ordinary case.
- Removal is a real delete, not retirement — a class is catalogue housekeeping, not a
  party to a booking. But a class that anything else still points at is refused with 409
  rather than cascading, so history is never destroyed by tidying the catalogue. Every
  table that comes to reference a vehicle class does so `ON DELETE RESTRICT`; since
  ticket 24 that includes vehicles, so removing a class that still has cars answers 409.
- Classes under a retired provider remain listable and fetchable, matching how retired
  providers themselves behave. Adding a class to a retired provider is also allowed:
  retirement stops new bookings, and this is not one.

### Vehicles

- A vehicle sits in exactly one vehicle class. It may be reclassified within the same
  provider's catalogue — a car really does move from Economy to Compact — but moving it
  to another provider's class is refused with 409: that is a sale, not a
  reclassification.
- Plates are unique across the whole system, not per provider, and compared without
  regard to case. A plate identifies a car on the road; the same one under two providers
  would mean one of them is wrong. A duplicate is refused with 409, guaranteed by a
  unique index on `lower(plate)`.
- The fleet is admin-only to read. A plate is fleet administration and of no use to a
  renter, who books a kind of car. What a renter needs is the count, reported as
  `vehicle_count` on the vehicle class itself and readable by any authenticated user.
- `vehicle_count` is computed on read by aggregation, never stored, for the same reason
  a provider's `average_rating` is: a stored count drifts the moment a car is added or
  removed outside the one code path that maintains it. It is the capacity that becomes
  enforceable in ticket 26; nothing yet refuses a booking because of it.
- Removing a vehicle is a real delete, but a car that anything else still points at — a
  maintenance blackout window, once ticket 39 lands — is refused with 409 rather than
  cascading. Every table that comes to reference a vehicle does so `ON DELETE RESTRICT`.
- A vehicle's own foreign key to its class is `ON DELETE RESTRICT`, which is what makes
  the vehicle class in-use refusal above real: removing a class that still has cars in it
  answers 409.

### Authorization

- Users and admins share the same routes. Scope widens by role: `GET /bookings` returns
  your own bookings, or all of them for an admin. The same widening applies to a booking
  addressed by identifier — fetching, re-dating and deleting all resolve through one
  lookup, so a registered user reaches only their own and an admin reaches any.
- Acting on a booking you do not own returns `404`, not `403`, so that booking ids
  cannot be enumerated. The answer is identical whatever the verb and whatever else is
  wrong with the request, so ordering cannot be used to probe either.
- Admin-only provider routes answer `403` rather than `404`, whether or not the provider
  exists: the role is resolved before the lookup, and provider existence is readable by
  any authenticated user anyway.

### Vehicle class surface

- Created under the provider (`POST /providers/{id}/vehicle_classes`), since a class
  cannot exist without one, and listed there (`GET /providers/{id}/vehicle_classes`,
  ordered by name then id). Thereafter addressed directly:
  `GET /vehicle_classes/{id}`, `PATCH /vehicle_classes/{id}`,
  `DELETE /vehicle_classes/{id}`.
- Editing is a `PATCH` because name and description are genuinely independent, as with
  providers.
- `DELETE /vehicle_classes/{id}` answers 204 with no body. It really removes the row.
- Reads are open to any authenticated caller; create, edit and remove are admin-only and
  answer 403, consistent with the provider routes they mirror.

### Vehicle surface

- Created and listed under the class (`POST` / `GET /vehicle_classes/{id}/vehicles`,
  ordered by plate then id), then addressed directly: `GET /vehicles/{id}`,
  `PATCH /vehicles/{id}`, `DELETE /vehicles/{id}`.
- Every one of those is admin-only and answers 403 to a registered user, reads included —
  the only route in the service where a read is privileged, because the plate is the
  privileged part.
- `DELETE /vehicles/{id}` answers 204 with no body.
- A `PATCH` naming a vehicle class that does not exist answers 422, not 404: the missing
  thing is a value in the body, not the resource the path addresses, and the vehicle
  itself was found.

### Booking surface

- Created under the provider (`POST /providers/{id}/bookings`), since a booking cannot
  exist without one. Thereafter addressed directly: `GET /bookings`,
  `GET /bookings/{id}`, `PUT /bookings/{id}`, `DELETE /bookings/{id}`.
- Re-dating is a `PUT` carrying both dates rather than a `PATCH` of either. A rental
  period is one value with two halves, so replacing it wholesale keeps the date rules on
  the request schema, where they answer 422, instead of validating a merge of stored and
  supplied values in the handler. Provider editing is a `PATCH` because its fields are
  genuinely independent.
- `DELETE /bookings/{id}` answers 204 with no body. Provider deletion answers 200 with the
  record because it retires rather than removes; this one really deletes.
- A booking response nests the provider and the vehicle class. The class is nested as a
  **summary** — id, provider, name, description — and deliberately without
  `vehicle_count`, because that number comes from an aggregate query rather than from the
  model and would otherwise be reported as a confident zero. The nested provider does not
  yet observe the same discipline: `average_rating` and `review_count` inside a booking
  are always `null` and `0`. That is a known defect, recorded as ticket 50.

## Auth

Stateless JWT, 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`), no refresh token. Logout is
client-side; the endpoint exists and invalidates nothing. Passwords are hashed with
bcrypt, minimum 8 characters and at most 72 bytes, never returned. Registration returns a
token directly.

The `bcrypt` library is used directly rather than through passlib, which this document
originally named: passlib's last release was 2020 and its bcrypt backend fails outright
against bcrypt 5.x, which it probes for a `__about__` attribute that no longer exists.
The alternative was pinning an old bcrypt to keep passlib working, and the password
hashing library is the last dependency worth freezing. The 72-byte ceiling is bcrypt's
own limit, not a policy choice; over-long passwords are rejected as unprocessable rather
than silently truncated.

`JWT_SECRET_KEY` must be at least 32 bytes, per RFC 7518 for HS256, and startup fails
otherwise: a short signing key is brute-forceable, and a forged token would defeat every
authorisation rule in the service. Logging in with an unknown email spends the same time
as a wrong password, so registered addresses cannot be found by timing the refusal.

Validation errors never echo a rejected password. Pydantic reports the offending value
alongside each error by default, which would put a plaintext password in a response body
and from there into logs and proxies; a handler redacts it and changes nothing else about
the error shape.

## Status codes

| Situation | Code |
|---|---|
| Fourth active booking | 409 |
| Booking a retired provider | 409 |
| Reviewing a booking that has not ended | 409 |
| Reviewing a booking twice | 409 |
| Registering an email that is already in use | 409 |
| Logging in with a wrong password or an unknown email | 401 (same response for both) |
| A missing, malformed, expired, or forged access token | 401 |
| Malformed input (date order, rating range, max length, password length) | 422 |
| Sending an unexpected field, such as `role`, on registration | 422 |
| Acting on another user's booking | 404 |
| An admin trying to create a booking of their own | 403 |
| Deleting a booking | 204, no body |
| Sending `provider_id` when re-dating a booking | 422 — refused, never silently ignored |
| A registered user on an admin-only provider route | 403, whether or not the provider exists |
| Re-dating a reviewed booking so it would not yet have ended | 409, reported ahead of the cap |
| A path id larger than an integer primary key can hold | 422 |
| Booking with no vehicle class, or one outside integer range | 422 |
| Booking a vehicle class that does not exist | 422 (a body value, not the path) |
| Booking a vehicle class belonging to a different provider | 409 |
| Booking a class whose vehicles are all taken on any day of the period | 409 |
| Booking a class that has no vehicles at all | 409 |
| Re-dating a booking into a period where its class is full | 409 |
| Sending `vehicle_class_id` when re-dating a booking | 422 — refused, never silently ignored |
| A duplicate vehicle class name under one provider, in any case | 409 |
| Removing a vehicle class that something still references | 409 |
| Sending `provider_id` when editing a vehicle class | 422 — refused, never silently ignored |
| A registered user on an admin-only vehicle class route | 403, whether or not the class exists |
| Removing a vehicle class | 204, no body |
| A duplicate plate anywhere in the system, in any case | 409 |
| Moving a vehicle to another provider's class | 409 |
| Naming a non-existent vehicle class when editing a vehicle | 422 (a body value, not the path) |
| Removing a vehicle that something still references | 409 |
| A registered user on any vehicle route, read or write | 403 |
| Removing a vehicle | 204, no body |

## Seeding and testing

`python -m app.seed` wipes and recreates demo data, and refuses to run when
`ENV=production`. It creates 3–4 providers including one retired, one admin, two users,
and for the demo user one ended booking (inserted through the ORM, bypassing the
no-past-dates rule) plus one upcoming booking. Since ticket 25 it also creates one vehicle
class per provider, and two for the first, because a booking cannot exist without one. It
creates vehicles for each of those classes — three, one, two and one — since ticket 26
made capacity real and a class with no cars refuses every booking. The counts differ on
purpose, so a demo can fill the one-car class and see the refusal without making three
bookings first. Ticket 47 rebuilds the fixture. It creates no reviews, so the demo
performs the first one.

Testing is a committed Postman collection only; there is no automated suite. Dates in
the collection are computed in pre-request scripts relative to now, never hardcoded, so
that requests do not go stale.
