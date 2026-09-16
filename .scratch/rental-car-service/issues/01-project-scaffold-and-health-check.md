# 01 — Project scaffold and health check

**What to build:** The service starts, reads its configuration from the environment,
connects to PostgreSQL, and answers a health check. Each developer gets their own
PostgreSQL through Docker Compose rather than sharing a cloud instance, because the seed
command wipes tables and a shared database would mean two people destroying each other's
demo data. The database schema is reproducible from empty by running migrations, and the
API's OpenAPI document can be imported into Postman as a working collection. Also lands
the shared helper that every later date rule depends on: the current date computed in
the configured business timezone, never from the system clock directly.

**Blocked by:** None — can start immediately

**Owner:** Time

**Status:** done — merged to main, audited. One criterion partly met, noted below.

- [x] The application starts and serves over HTTP
- [x] A Docker Compose file stands up a PostgreSQL service with one command, with a named
      volume so data survives a restart and a pinned major version so both developers run
      the same one
- [x] The committed example environment file points at the Compose database by default, so
      a fresh clone runs without editing configuration
- [x] The README records the two commands needed from a clean checkout: bring the database
      up, then run migrations
- [x] No shared or cloud database is required for development; each developer runs their
      own, since the seed command wipes tables
- [x] Configuration is read from the environment: database URL, JWT signing key, token
      lifetime in minutes, business timezone, and an environment name
- [x] Secrets live in an untracked environment file; a tracked example file lists every
      variable with placeholder values; no signing key is committed
- [x] A health endpoint reports that the service is up and that the database is reachable
- [x] Migrations are set up and an initial migration applies cleanly against an empty
      database
- [x] The module layout is feature-first, one module per area, with a single place that
      imports every model so migration autogeneration sees all tables
- [x] A shared helper returns today's date in the configured business timezone; no other
      code computes the current date directly
- [x] The OpenAPI document is served and imports into Postman without errors
- [x] Responses are snake_case bare resources with the framework's default error shape;
      no success/data envelope

### The Postman import, finally verified

Confirmed by hand on 2026-09-17: Postman imports the served document without errors and
produces a collection. This was the only unverified criterion on any closed ticket, open
since this ticket first shipped.

The concern behind it turned out to be unfounded. FastAPI emits OpenAPI **3.1.0**, and
Postman's support for 3.1 had historically lagged 3.0, so the import was left unticked
rather than claimed. Current Postman accepts it.

Two things that follow:

- The contingency plan recorded here earlier — pinning the emitted version to 3.0.x — is
  moot, and was wrong anyway: it leaves the schema 3.1-shaped, with optional fields still
  rendered as `anyOf` containing `type: null`, which 3.0 has no concept of.
- **Ticket 22 can start from the generated collection** rather than building sixteen
  requests by hand. The import is only a scaffold: it carries every endpoint with the right
  method and path, but placeholder bodies, no captured token, static dates and no
  assertions. The variables, pre-request date scripts, token capture and negative cases are
  still that ticket's work.

