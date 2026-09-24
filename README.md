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
| `ENV` | `local` | Environment name |

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
alembic/       migration environment and versions
```

`app/core/clock.py` is the only place that computes the current date. No other module
may call `date.today()`; every date rule goes through `today()` so the whole service
agrees on which day it is in the configured business timezone.

Responses are snake_case bare resources. Errors use FastAPI's default `{"detail": ...}`
shape. There is no success/data envelope.
