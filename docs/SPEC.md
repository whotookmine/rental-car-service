# Rental Car Service — Agreed Design

Terminology is defined in [CONTEXT.md](../CONTEXT.md). Decisions with lasting
consequences are recorded in [docs/adr](./adr). This file is the working specification:
the rules, the surface, and the shape of the system as agreed.

## Stack

Python, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, PostgreSQL. Feature-first layout
(`auth/`, `bookings/`, `providers/`, `reviews/`), with a single `app/db/base.py` that
imports every model so Alembic autogeneration sees all tables. JSON is snake_case, bare
resources, FastAPI's default `{"detail": ...}` error shape with self-explaining messages.

## Entities

There is no Car entity. A booking reserves a period with a provider.

- **User** — name, telephone, email (unique, lowercased), password hash, role
  (`user` | `admin`, defaults to `user`, never settable through the API).
- **Provider** — name, address, telephone, `is_retired`.
- **Booking** — user, provider, `start_date`, `end_date` (both `DATE`).
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
- A booking cannot be created against a retired provider (409). Existing bookings made
  before retirement are unaffected and remain viewable. Reinstating the provider makes it
  bookable again.
- Overlapping bookings by the same user are allowed. With no vehicle inventory they
  contradict nothing, and the active cap already bounds abuse.
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

## Seeding and testing

`python -m app.seed` wipes and recreates demo data, and refuses to run when
`ENV=production`. It creates 3–4 providers including one retired, one admin, two users,
and for the demo user one ended booking (inserted through the ORM, bypassing the
no-past-dates rule) plus one upcoming booking. It creates no reviews, so the demo
performs the first one.

Testing is a committed Postman collection only; there is no automated suite. Dates in
the collection are computed in pre-request scripts relative to now, never hardcoded, so
that requests do not go stale.
