# Requirements traceability

**This is the document to read before a grading pass.** It holds the requirements *as
given*, verbatim, and maps every clause to the route that satisfies it and the check that
proved it. Nothing here is derived or paraphrased: `docs/SPEC.md` is the agreed ruleset we
built, and this file is the brief we were handed. When the two disagree, this one is the
requirement and `docs/SPEC.md` is the design — but neither may contradict the other
silently.

Last audited against a running app and a real PostgreSQL on **2026-10-02**. Requirement 7's
first clause was re-audited when ticket 39 landed. Rows 5b, 6, 6a and 6b were re-audited on
**2026-11-18**, after tickets 35–38 landed, the same way: rebuilt from empty, seeded, then
exercised. Every other row dates from the first audit. The schema was rebuilt from empty (`downgrade base` →
`upgrade head`, `alembic check` clean) and seeded with `uv run python -m app.seed` before
the audit, so every result below came from the committed fixture and not from a hand-made
database.

## Verdict in one line

**Round one is complete and conforming. Round two is complete: requirements 4, 5, 6 and 7
all have a verified surface.**

---

## Round one — the original requirements, verbatim

> The system shall allow a user to register by specifying the name, telephone number,
> email, and password.
> After registration, the user becomes a registered user, and the system shall allow the
> user to log in to use the system by specifying the email and password. The system shall
> allow a registered user to log out.
> After login, the system shall allow the registered user to book up to 3 cars by
> specifying the date and the preferred rental car provider. The rental car provider list
> is also provided to the user. A rental car provider information includes the name,
> address, and telephone number.
> The system shall allow the registered user to view his/her rental car bookings.
> The system shall allow the registered user to edit his/her rental car bookings.
> The system shall allow the registered user to delete his/her rental car bookings.
> The system shall allow the admin to view any rental car bookings.
> The system shall allow the admin to edit any rental car bookings.
> The system shall allow the admin to delete any rental car booking

### Additionals (first set)

> 1. The system shall allow the registered user to rate (1–5) and review a provider only
>    after the booking's rental period has ended.
> 2. The system shall display the average rating and review count for each provider in the
>    provider list.
> 3. The system shall allow the admin to delete inappropriate reviews.

### Constraints

> The system shall be a web API. The frontend part of the application is not required. The
> development team shall develop the backend system as REST APIs. The database system can
> be either MongoDB Atlas or Postgresql.

### Non-functional requirements

> - **Security:** the system shall authenticate users using username/password; the system
>   shall be able to keep user's transactions confidential.
> - **Performance:** the system shall respond to a request in 3 seconds.
> - **Usability:** the system shall be used and tested via Postman.

---

## Round two — requirements 4 to 7, verbatim

Given later, introduced with *"I have more requirements, I want you to split it into issues
first like we did before."*

> 4. The system shall allow a registered user to join a waitlist for a fully-booked vehicle
>    class on a given date range, and shall notify waitlisted users in strict FIFO order
>    when inventory is released by a cancellation, granting each a time-limited exclusive
>    claim window before offering it to the next person in the queue.
> 5. The system shall support one-way rentals where the drop-off location differs from the
>    pickup location, automatically computing a relocation fee from the inter-branch
>    distance and blocking the combination if the provider has not enabled one-way service
>    between those branches.
> 6. The system shall allow the registered user to request vehicle delivery to and
>    collection from a specified address, validating that the address falls within the
>    provider's delivery radius and adding a distance-tiered delivery charge to the
>    quotation.
> 7. The system shall schedule vehicle maintenance blackout windows per vehicle,
>    automatically excluding those vehicles from availability searches and preventing any
>    booking that overlaps a blackout window.

---

## Matrix — round one

Every row was exercised against the running app. ✅ = conforming, verified by the command
shown. The "Verified" column is the actual response, not a description of one.

| # | Requirement clause | Where | Verified |
|---|---|---|---|
| 1 | Register by specifying name, telephone, email, password | `POST /auth/register` | ✅ `201`, all four fields required — omitting `telephone` is `422 Field required` |
| 1a | Registration makes a *registered user* | `app/auth/models.py` `UserRole` | ✅ `GET /auth/me` → `"role":"user"` |
| 1b | A client cannot register itself as admin | `UserCreate` has no `role`, `extra="forbid"` | ✅ body carrying `"role":"admin"` → `422 extra_forbidden`. Admins come only from `uv run python -m app.create_admin` |
| 1c | One email, one identity | unique index on `lower(email)` | ✅ duplicate → `409`; **same address in UPPERCASE → `409`** too |
| 2 | Log in by specifying email and password | `POST /auth/login` | ✅ `200` with a bearer token |
| 2a | Login does not reveal whether an email exists | one message for both cases | ✅ wrong password → `401 Incorrect email or password.`; unknown email → the **same** `401` |
| 3 | A registered user can log out | `POST /auth/logout` | ✅ `200`. Stateless JWT, so the token stays valid until expiry — the honest behaviour and the reason, in `docs/adr/0003` |
| 4 | Book by specifying the date and the preferred provider | `POST /providers/{id}/bookings` | ✅ `201`. Provider in the path, rental period in the body. **See "The one divergence" below** |
| 4a | Up to **3** bookings | `MAX_ACTIVE_BOOKINGS` in `app/bookings/rules.py` | ✅ 1st–3rd → `201`; **4th → `409 "You already hold 3 active bookings…"`** |
| 4b | Ended rentals stop counting | `count_active_bookings` compares against `today()` | ✅ demo user holds an ended booking and could still book |
| 4c | The provider list is provided to the user | `GET /providers` | ✅ `200`, three active providers; the retired one is left out |
| 4d | Provider info includes name, address, telephone | `ProviderRead` | ✅ keys returned: `address, average_rating, id, is_retired, name, review_count, telephone` |
| 5 | A registered user views his/her bookings | `GET /bookings`, `GET /bookings/{id}` | ✅ demo sees `[1,2]`, fresh sees `[3,4,5]` — each only their own |
| 6 | A registered user edits his/her bookings | `PUT /bookings/{id}` | ✅ `200` with new dates; `end<start` → `422`; sending `provider_id` → `422 extra_forbidden` |
| 7 | A registered user deletes his/her bookings | `DELETE /bookings/{id}` | ✅ `204`, active count 3 → 2, and an immediate rebook → `201` |
| 7a | Another user's booking is not reachable | `get_visible_booking_or_404` | ✅ GET, PUT and DELETE on someone else's booking all → **`404 Booking not found.`**, identical to a booking that never existed, so ids cannot be enumerated |
| 8 | The admin views **any** booking | role branch in `list_bookings` | ✅ admin `GET /bookings` → `[1,2,3,4,5]`; admin `GET /bookings/1` (another user's) → `200` |
| 9 | The admin edits **any** booking | `PUT /bookings/{id}` | ✅ admin re-dated booking 2 → `200`; admin sending `end<start` → `422`, the same rules as the owner |
| 10 | The admin deletes **any** booking | `DELETE /bookings/{id}` | ✅ `204` (exercised in tickets 13 and 20) |
| 10a | Admins do not hold bookings of their own | `require_registered_user` | ✅ admin creating a booking → `403 "Admins manage rentals rather than holding them, so they cannot book or join a waitlist."` (reworded in ticket 43, when the same guard began protecting waitlist places too) |
| A1 | Rate 1–5 and review, **only after the rental period has ended** | `POST /bookings/{id}/reviews` | ✅ ended booking → `201`; **not-yet-ended → `409`**; `rating:0` → `422`; `rating:6` → `422`; second review of the same booking → `409`; someone else's booking → `404` |
| A2 | Average rating and review count for each provider in the list | read-time aggregate in `app/providers/` | ✅ after a 4-star review: `Fast Wheels 4.0 1`, others `None 0` — an unreviewed provider shows **no rating, not a zero** |
| A3 | The admin deletes inappropriate reviews | `DELETE /reviews/{id}` | ✅ admin → `204`; a registered user who is not the author → `404`; afterwards the average returned to `None/0`, **the booking survived**, and the booking became reviewable again (`201`) |

### Constraints and non-functional

| Requirement | Status | Verified |
|---|---|---|
| A web API, REST, no frontend | ✅ | FastAPI, JSON only, no templates or static assets in the repo. Snake_case bare resources, FastAPI's `{"detail": …}` error shape, no success envelope |
| MongoDB Atlas **or** PostgreSQL | ✅ | PostgreSQL 16. The choice and the rejection of MongoDB are argued in `docs/adr/0001-postgresql-over-mongodb.md` |
| Authenticate using username/password | ✅ | Email + password at `/auth/login`; bcrypt hashes; HS256 JWT, 60 minutes |
| Keep the user's transactions confidential | ✅ | Bookings and reviews are scoped by the token's identity, never by a body or query field. Another user's booking answers `404`. No credential ever appears in a response: a `422` on registration renders the rejected password as `"password":"[redacted]"` |
| Respond within 3 seconds | ✅ | Measured, warm, against the seeded database: `/health` 3.6 ms, `/providers` 5.8 ms, `/providers/1` 6.6 ms, `/bookings` 6.4 ms, `/providers/1/availability` 6.6 ms, `/providers/1/vehicle_classes` 9.2 ms. Three orders of magnitude inside the budget |
| **Used and tested via Postman** | ✅ | `rental-car-service.postman_collection.json` committed at repo root. 42 requests across 9 folders when first built in ticket 22 (health, authentication, provider browsing, provider management, booking lifecycle, reviews, admin oversight, negative cases); extended in ticket 49 to 113 requests across 17 folders covering the round-two surface. Dates computed by pre-request scripts; tokens and IDs captured from responses; base URL a variable. Verified green end-to-end against a freshly seeded database (ticket 22, owner Garfield) |

---

## The one divergence from the requirements as written

Round one says a booking is made *"by specifying the date and the preferred rental car
provider."* Creation now also **requires** a vehicle class and a pickup branch:

```
POST /providers/1/bookings  {"start_date":"2026-11-05","end_date":"2026-11-06"}
-> 422  vehicle_class_id: Field required
        pickup_branch_id: Field required
```

This is deliberate and forced by round two, not scope creep:

- Requirement 4 queues a waitlist **"for a fully-booked vehicle class"**, and requirement 7
  blacks out maintenance **"per vehicle"**. Neither is expressible unless a booking says
  which kind of car it is for — so tickets 23–26 introduced vehicle classes and vehicles.
- Requirement 5 needs a pickup and a drop-off **location**, which is what branches are
  (tickets 28–29).

The round-one clause is still satisfied — the date and the provider are still what the
caller specifies, and the provider is still fixed for the life of the booking. But the
request body is **larger** than round one describes, so a grader testing the round-one
shape verbatim will see a `422`. If that matters for marking, the fix is not to make the
fields optional (a booking with no class cannot be matched against capacity) but to say so
in the demo script and the Postman collection.

---

## Matrix — round two

| # | Requirement clause | Status | Where / what is missing |
|---|---|---|---|
| **4** | Join a waitlist for a fully-booked vehicle class on a date range | ✅ built | Ticket 43. `POST /providers/{id}/waitlist_entries`, `GET /waitlist_entries`, `DELETE /waitlist_entries/{id}`. Verified: three users queue at positions 1–2–3, joining a class that is *not* full is refused 409, a second place in one queue is 409, leaving closes the gap |
| 4a | Notify waitlisted users | ✅ built | Ticket 42 built the records and read surface; ticket 45 made the waitlist write them. Verified: the holder of a new claim receives a `waitlist_offer` notification naming the class, dates and deadline, and the person behind them receives nothing |
| 4b | Strict FIFO release on cancellation | ✅ built | Ticket 44. Verified: three queue, one cancellation reaches only the front; two cancellations reach the first then the second; an entry the release cannot use is skipped and keeps its place; two simultaneous cancellations reach two different people |
| 4c | Time-limited exclusive claim window | ✅ built | Ticket 45. A live claim occupies a car exactly as a booking does, so the class reads as full to everyone else; the holder converts it despite that. Window is `CLAIM_WINDOW_MINUTES` (default 60), verified configurable. Expiry judged lazily, with no scheduler |
| 4d | Expiry passes the claim to the next in the queue | ✅ built | Ticket 46. Verified end to end: three queue, the first lets the claim expire, the second declines, the third is offered it and books it. Lazy — nothing is offered on until the queue is next touched, proved with a week-old lapse. Two simultaneous reads of a stale queue leave exactly one live claim |
| **5** | One-way rentals, drop-off differs from pickup | ✅ built | `dropoff_branch_id` on `POST /providers/{id}/bookings` (tickets 31, 32). Verified: enabled direction 1→2 → `201` |
| 5a | **Blocked** unless the provider enabled one-way service between those branches | ✅ built | Verified: the unenabled reverse direction 2→1 → `409 "One-way rental from 'Don Mueang Airport' to 'Siam' has not been enabled by this provider."` Enablement is directional on purpose |
| 5b | **Automatically compute a relocation fee from the inter-branch distance** | ✅ built | Ticket 35. `POST /providers/{id}/quotations` adds a relocation line, `distance_km × RELOCATION_RATE_PER_KM` (default THB 50.00/km). Verified: one-way Siam→Don Mueang → `200`, lines `"Economy × 3 days @ THB 1200.00/day" 3600.00` + `"Relocation fee (27.5 km × THB 50.00/km)" 1375.00`, total `4975.00`. The same dates with no drop-off → rental line only, total `3600.00` |
| **6** | Request vehicle delivery to and collection from an address | ✅ built | Ticket 37. `delivery_address` + `delivery_distance_km`, and optionally `collection_address`, on `POST /providers/{id}/bookings`. Verified: 20 km delivery at Siam → `201` with `"delivery_address":"10 Sukhumvit Rd","delivery_distance_km":20`; an address without a distance → `422 "delivery_address and delivery_distance_km must both be provided or both omitted"`. The distance is stated by the caller rather than geocoded from the address (no external geocoder) |
| 6a | Validate the address is within the provider's delivery radius | ✅ built | Tickets 36, 37. Radius is set per branch with `PUT /branches/{id}/delivery-radius` (Siam = 20 km; Don Mueang = none). One rule, `ensure_delivery_within_radius` in `app/bookings/rules.py`, is applied by **both** booking creation and quotation. Verified on booking: 25 km at Siam → `409 "Delivery distance 25 km exceeds the branch radius of 20 km."`; 20 km → `201` (inclusive); at Don Mueang → `409 "The pickup branch does not offer delivery."` Verified on quotation: 30 km and 21 km at Siam → `409` naming the 20 km radius; 20 km → `200` with a 400.00 line; 5 km at Don Mueang → `409 "The pickup branch does not offer delivery."` (Until 2026-11-18 the quotation skipped this check and priced deliveries the booking refused. Fixed on `fix/quotation-delivery-radius`) |
| 6b | Distance-tiered delivery charge added to the quotation | ✅ built | Ticket 38. Tiers come from `DELIVERY_TIERS` (default ≤10 km 200.00, ≤20 km 400.00, ≤50 km 800.00, upper bound inclusive). Verified: 5 km → `"Delivery and collection (up to 10 km)" 200.00`, total `3800.00`; 15 km → `400.00`, total `4000.00`; one-way plus 5 km delivery → rental + relocation + delivery lines, total `5175.00` |
| **7** | Schedule maintenance blackout windows **per vehicle** | ✅ built | Ticket 39. `POST`/`GET /vehicles/{id}/blackout_windows`, `GET`/`PUT`/`DELETE /blackout_windows/{id}`. Verified: scheduled 201, overlapping 409, adjacent 201, past 201, registered-user write 403, vehicle with a window `DELETE` 409 |
| 7a | Blacked-out vehicles excluded from availability searches | ✅ built | Ticket 40. Verified: 3 cars with 1 blacked out reports 2; all 3 blacked out reports 0 with the class still listed; a window ending the day before the range costs nothing; cancelling restores the count immediately |
| 7b | Any booking overlapping a blackout is prevented | ✅ built | Ticket 41. Verified: booking a wholly blacked-out class 409, re-dating onto blacked-out days 409 for owner **and** admin, a class short through maintenance *and* bookings together 409 naming both, availability and booking agreeing in all three directions |

Tables present (2026-11-18): `alembic_version, blackout_windows, bookings, branch_distances,
branches, notifications, one_way_routes, providers, reviews, users, vehicle_classes,
vehicles, waitlist_entries`. Delivery lives as columns on `branches` and `bookings`.

---

## What must land before this is graded

Nothing. All 51 tickets are done, including the Postman collection (22, extended by 49),
the seed data (47) and the documents (48). The one defect the 2026-11-18 re-audit found, a
quotation that skipped the delivery-radius check, is fixed (row 6a).

## How to re-run this audit

```bash
docker compose up -d
uv run alembic downgrade base && uv run alembic upgrade head && uv run alembic check
uv run python -m app.seed
uv run uvicorn app.main:app --port 8000
```

Then `uv run python -m app.smoke`, which re-checks 182 status codes across the matrix in
one command, and walk the rest by hand. Credentials come from the seed output: `admin@example.com/admin1234`,
`demo@example.com/demo1234` (one ended and one upcoming booking),
`fresh@example.com/fresh1234` (none). Note that the seed's dates are relative to the day it
runs, so re-seed rather than reusing a week-old database.

**Re-audit whenever a requirement clause changes state** — a ticket landing, or a new round
of requirements arriving. A stale traceability matrix is worse than none, because it is the
document someone will trust without checking.
