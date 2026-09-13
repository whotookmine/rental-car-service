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
- [ ] The OpenAPI document is served and imports into Postman without errors
      — **partly done.** The document is served and is valid OpenAPI 3.1.0, but the
      Postman import itself has not been tried. FastAPI emits 3.1.0 and Postman's
      support for 3.1 has lagged 3.0; if the import fails, pin the emitted OpenAPI
      version to 3.0.x. Verify before starting ticket 22, which depends on it.
- [x] Responses are snake_case bare resources with the framework's default error shape;
      no success/data envelope
