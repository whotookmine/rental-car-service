# Rental Car Service

A web API through which registered users reserve cars from rental car providers for a
period of time, and afterwards rate the provider they rented from.

Terminology lives in [CONTEXT.md](./CONTEXT.md), the agreed ruleset in
[docs/SPEC.md](./docs/SPEC.md), and the binding decisions in [docs/adr](./docs/adr).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — manages the Python toolchain, the virtual
  environment, and dependencies. It installs a suitable Python itself, so no separate
  Python install is required.
- Docker with Docker Compose v2

No shared or cloud database is used. Each developer runs their own PostgreSQL through
Docker Compose, because the seed command wipes tables and a shared database would mean
two people destroying each other's demo data.

## From a clean checkout

Install the dependencies. `uv sync` creates `.venv` and installs the exact versions
pinned in `uv.lock`, so everyone runs the same ones:

```bash
uv sync
```

Copy the example environment file — its defaults already point at the Compose database,
so nothing needs editing to get running:

```bash
cp .env.example .env
```

Then the two commands:

```bash
docker compose up -d          # 1. bring the database up
uv run alembic upgrade head   # 2. run migrations
```

`uv run` executes inside the project environment, so there is nothing to activate.

## Admin account

Admins cannot be created through the API. Use the provisioning command instead:

```bash
uv run python -m app.create_admin
```

This creates an admin with email `admin@example.com` and password `admin1234`. Running
the command again with the same email is safe — it prints a message and exits without
making changes. To use different credentials:

```bash
uv run python -m app.create_admin --email you@example.com --password yourpassword
```

The admin can then log in through `POST /auth/login` and receives a token like any other
user. Only admins may create and edit providers.

## Running the app

```bash
uv run uvicorn app.main:app --reload --port 8000
```

- Health check: <http://127.0.0.1:8000/health> — returns `200` when the service is up
  and the database answers a query, and `503` when the database is unreachable.
- OpenAPI document: <http://127.0.0.1:8000/openapi.json> (import this URL into Postman
  to get a working collection).
- Interactive docs: <http://127.0.0.1:8000/docs>.

## Demo

### Credentials

After running `uv run python -m app.seed`:

| Account | Email | Password | Notes |
|---|---|---|---|
| Admin | `admin@example.com` | `admin1234` | Can create and edit providers, see all bookings, delete any review |
| Demo user | `demo@example.com` | `demo1234` | Has one ended booking (reviewable) and one upcoming booking; two seeded notifications |
| Clean user | `fresh@example.com` | `fresh1234` | No bookings — useful for demonstrating registration and the booking flow from scratch |
| Alpha | `alpha@example.com` | `alpha1234` | Holds the only SUV booking (today+3 to today+10), which fills that class |
| Beta | `beta@example.com` | `beta1234` | Waitlist position 1 for SUV (same range as alpha's booking) |
| Gamma | `gamma@example.com` | `gamma1234` | Waitlist position 2 for SUV |

### Postman collection

Import `rental-car-service.postman_collection.json` into Postman. Run the folders in order:

1. **00 — Setup** — must run first. Logs in as all six accounts (admin, demo, fresh, alpha, beta, gamma) and calls the API to discover every ID the later folders depend on.
2. **01 — Health** — confirms the API and database are up.
3. **02 — Authentication** — register a new account, log in, inspect the token holder, log out. Logout is client-side: the server invalidates nothing. See the architecture decision on stateless tokens in `docs/adr/`.
4. **03 — Provider Browsing** — list active providers (with ratings), inspect a single provider, observe that the retired provider appears only with an admin token.
5. **04 — Provider Management (Admin)** — create a provider, edit its details, retire it, reinstate it.
6. **05 — Booking Lifecycle** — create two bookings for the demo user, list and inspect them, re-date one. Creating a booking requires `vehicle_class_id` and `pickup_branch_id`; the Setup folder discovers these IDs automatically.
7. **06 — Reviews** — create a review on the demo user's ended booking, edit it, delete it. The ended booking is reviewable; an active booking is not.
8. **07 — Admin Oversight** — admin's view of all bookings, and admin deletion of any review.
9. **08 — Negative Cases** — the three-booking cap, reversed dates, 31-day limit, past start date, booking a retired provider, reviewing before the period ends, a second review, and one user reaching for another user's booking.
10. **09 — Availability** — `GET /providers/{id}/availability` returns free counts per class. Shows the seeded Economy blackout reducing the count from 3 to 2, and the alpha booking making SUV free_count=0.
11. **10 — Fleet (Admin)** — vehicle class and vehicle CRUD. Vehicle reads are admin-only (plates are fleet administration, not renter information).
12. **11 — Branches, Distances & One-Way** — list branches, inspect delivery radii, record a distance, enable/disable one-way routes. Negative case: Airport→Siam refused because only Siam→Airport is enabled in the seed.
13. **12 — Quotations** — price estimates without reserving capacity. Demonstrates the rental line, the relocation line (one-way), and the delivery line. Unpriced class → 409.
14. **13 — Delivery Bookings** — create a booking with `delivery_address` and `delivery_distance_km`. Negative cases: distance beyond radius (409), branch with no delivery radius (409), missing one half of the delivery pair (422).
15. **14 — Maintenance (Blackout Windows)** — create a window on the SUV vehicle, show availability drops to 0, show booking refused, show overlap conflict, then delete the window and confirm availability restored.
16. **15 — Waitlist & Claims** — full FIFO chain: alpha cancels → beta gets offered → beta declines → gamma gets offered → gamma converts. Negative cases: booking a full class, joining a non-full class, converting a claim twice.
17. **16 — Notifications** — list the demo user's seeded notifications (newest first), mark one read (idempotent), reach for another user's notification (404).

The base URL is a collection variable (`base_url`, default `http://localhost:8000`). All dates are computed by a collection-level pre-request script and are never hard-coded, so the collection does not go stale.

### The one divergence from the original brief

The brief was written before vehicle classes and pickup branches existed. Creating a booking now requires `vehicle_class_id` and `pickup_branch_id` alongside the dates — a round-one shaped body (dates only) answers `422`. The Setup folder discovers the correct IDs from the seeded data automatically; nothing needs to be filled in by hand. `docs/REQUIREMENTS-TRACE.md` records the reasoning under "The one divergence".

### Two rules that need the seeded ended booking

Two constraints cannot be shown by watching the API return an error; they are shown by watching it succeed where a naive implementation would fail:

- **Ended bookings do not count toward the three-booking cap.** At the point the negative case fires, the demo user holds one ended booking and three active ones. The fourth active booking attempt is refused at 409. If ended bookings counted, the limit would have been reached one attempt earlier. The collection says so in the relevant request description.
- **Ended bookings are reviewable.** The review creation in folder 06 succeeds with 201. If the booking were still considered active, the service would refuse with 409 ("rental period has not ended yet"). The collection says so there too.

## Smoke run

With the app running and the database seeded:

```bash
uv run python -m app.smoke
```

It calls the real API over HTTP and checks the status code of every answer — 182 checks
across authentication, providers, the booking lifecycle, capacity, one-way rentals,
reviews, admin oversight and the admin-only fleet routes, negative cases included.

```
182/182 checks passed, 0 skipped
```

It asserts **status codes only**, on purpose: response shapes change as the model grows,
status codes do not, so a failure here is always a real one. It is not an automated test
suite — there is none, by decision — and it does not replace the Postman collection, which
is what demonstrates behaviour to a reader. See the Verification table in `docs/SPEC.md`.

Points worth knowing:

- It needs nothing configured. `SMOKE_BASE_URL` overrides the default
  `http://localhost:8000`.
- It registers its own `smoke-*@example.com` users and deletes every booking and review it
  creates, so it can be run repeatedly without re-seeding. The seeded `admin`, `demo` and
  `fresh` accounts are left usable for a demo.
- Exit codes: `0` everything passed, `1` a check failed, **`2` the preconditions were not
  met** — usually `uv run python -m app.seed` is all it wants. A `2` is not a test failure.

## Configuration

Every variable is listed in `.env.example` with a placeholder value. `.env` is untracked
and no real signing key is committed. A missing `DATABASE_URL` or `JWT_SECRET_KEY`
aborts startup.

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | Compose database | SQLAlchemy PostgreSQL URL |
| `JWT_SECRET_KEY` | *(none — required)* | Signing key for access tokens |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `BUSINESS_TIMEZONE` | `Asia/Bangkok` | Timezone that defines the business day |
| `CURRENCY` | `THB` | ISO-4217 currency code used on all monetary amounts |
| `RELOCATION_RATE_PER_KM` | `50.00` | THB per km charged on one-way rentals |
| `DELIVERY_TIERS` | See SPEC | JSON array of `{"max_km": N, "charge": "X.XX"}` tiers for delivery pricing |
| `CLAIM_WINDOW_MINUTES` | `60` | How long a waitlist claim is held for whoever it was offered to. Set to `1` to demonstrate expiry |
| `ENV` | `local` | Environment name — seed refuses to run when set to `production` |

Alembic reads `DATABASE_URL` from the same settings object as the app; `alembic.ini`
carries no URL of its own.

## Dependencies

Direct dependencies are declared in `pyproject.toml`; `uv.lock` pins the entire
resolved tree and **is committed**, so both developers and any grader install byte-identical
versions. Add a dependency with `uv add <package>`, which updates both files. Never
`pip install` into `.venv` directly — it would drift from the lockfile.

## Layout

```
app/
  core/        config (environment settings) and clock (the single today() helper)
  db/          engine/session, declarative base, and base.py which imports every model
  health/      the health check
  auth/        feature packages, one per area, each owning its own
  providers/     model, schemas, router and rules. Empty until their own tickets.
  bookings/
  reviews/
  vehicle_classes/  the kinds of car each provider rents out
  vehicles/      the individual cars in each class
alembic/       migration environment and versions
```

`app/core/clock.py` is the only place that computes the current date. No other module
may call `date.today()`; every date rule goes through `today()` so the whole service
agrees on which day it is in the configured business timezone.

Responses are snake_case bare resources. Errors use FastAPI's default `{"detail": ...}`
shape. There is no success/data envelope.
