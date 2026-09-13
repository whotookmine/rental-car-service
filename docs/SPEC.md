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

Dates are `DATE` columns with no time component. "Today" is computed in the configured
business timezone (`BUSINESS_TIMEZONE`, `Asia/Bangkok`) via a single `today()` helper.
No rule may call `date.today()` directly.

## Rules

### Bookings

- `end_date >= start_date`.
- Rental period is at most 30 days.
- `start_date` must not be in the past **on creation**. Updates may touch past dates, so
  that a booking already underway can be extended and an admin can correct history.
- A registered user may hold at most 3 **active** bookings (rental period not yet ended).
  Deleting a booking frees a slot immediately.
- Overlapping bookings by the same user are allowed. With no vehicle inventory they
  contradict nothing, and the active cap already bounds abuse.
- Only the dates are mutable, for owner and admin alike. The provider is fixed at
  creation.
- Every edit is validated identically whether the owner or an admin makes it: date
  ordering, the 30-day maximum, and the 3-active cap, the last measured against the
  booking's owner. Admins have wider scope, not weaker rules, and share the same code
  path. The accepted cost is that an admin cannot extend an ended booking for a user who
  already holds 3 active ones, even to correct a genuine error.
- A booking that has a review cannot be edited such that its rental period would no
  longer be ended (409). This applies to owners and admins alike; it keeps every review
  in the table attached to a finished rental.
- Admins do not hold bookings.

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
  `review_count` for each.
- `average_rating` is computed on read by aggregation, never stored. A provider with no
  reviews returns `null`, not `0`. Rounded to one decimal place in responses, stored at
  full precision.
- `GET /providers/{id}` returns retired providers too, so users can see who they booked.
- `DELETE /providers/{id}` retires; it never removes the row.

### Authorization

- Users and admins share the same routes. Scope widens by role: `GET /bookings` returns
  your own bookings, or all of them for an admin.
- Acting on a booking you do not own returns `404`, not `403`, so that booking ids
  cannot be enumerated.

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
| Malformed input (date order, rating range, max length, password length) | 422 |
| Sending an unexpected field, such as `role`, on registration | 422 |
| Acting on another user's booking | 404 |

## Seeding and testing

`python -m app.seed` wipes and recreates demo data, and refuses to run when
`ENV=production`. It creates 3–4 providers including one retired, one admin, two users,
and for the demo user one ended booking (inserted through the ORM, bypassing the
no-past-dates rule) plus one upcoming booking. It creates no reviews, so the demo
performs the first one.

Testing is a committed Postman collection only; there is no automated suite. Dates in
the collection are computed in pre-request scripts relative to now, never hardcoded, so
that requests do not go stale.
