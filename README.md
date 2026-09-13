# Rental Car Service

A web API through which registered users reserve cars from rental car providers for a
period of time, and afterwards rate the provider they rented from.

Terminology lives in [CONTEXT.md](./CONTEXT.md), the agreed ruleset in
[docs/SPEC.md](./docs/SPEC.md), and the binding decisions in [docs/adr](./docs/adr).

## Prerequisites

- Python 3.11 or newer
- Docker with Docker Compose v2

No shared or cloud database is used. Each developer runs their own PostgreSQL through
Docker Compose, because the seed command wipes tables and a shared database would mean
two people destroying each other's demo data.

## From a clean checkout

Copy the example environment file first — its defaults already point at the Compose
database, so nothing needs editing to get running:

```bash
cp .env.example .env
```

Then the two commands:

```bash
docker compose up -d   # 1. bring the database up
alembic upgrade head   # 2. run migrations
```

Install the dependencies into a virtual environment before step 2:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Running the app

```bash
uvicorn app.main:app --reload --port 8000
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
alembic/       migration environment and versions
```

`app/core/clock.py` is the only place that computes the current date. No other module
may call `date.today()`; every date rule goes through `today()` so the whole service
agrees on which day it is in the configured business timezone.

Responses are snake_case bare resources. Errors use FastAPI's default `{"detail": ...}`
shape. There is no success/data envelope.
