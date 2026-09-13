# 01 — Project scaffold and health check

**What to build:** The service starts, reads its configuration from the environment,
connects to PostgreSQL, and answers a health check. Each developer gets their own
PostgreSQL through Docker Compose rather than sharing a cloud instance, because the seed
command wipes tables and a shared database would mean two people destroying each other's
demo data. The database schema is reproducible from empty by running migrations, and the API's OpenAPI document can be imported into
Postman as a working collection. Also lands the shared helper that every later date rule
depends on: the current date computed in the configured business timezone, never from the
system clock directly.

**Blocked by:** None — can start immediately

**Owner:** Time

**Status:** ready-for-agent

- [ ] The application starts and serves over HTTP
- [ ] A Docker Compose file stands up a PostgreSQL service with one command, with a named
      volume so data survives a restart and a pinned major version so both developers run
      the same one
- [ ] The committed example environment file points at the Compose database by default, so
      a fresh clone runs without editing configuration
- [ ] The README records the two commands needed from a clean checkout: bring the database
      up, then run migrations
- [ ] No shared or cloud database is required for development; each developer runs their
      own, since the seed command wipes tables
- [ ] Configuration is read from the environment: database URL, JWT signing key, token
      lifetime in minutes, business timezone, and an environment name
- [ ] Secrets live in an untracked environment file; a tracked example file lists every
      variable with placeholder values; no signing key is committed
- [ ] A health endpoint reports that the service is up and that the database is reachable
- [ ] Migrations are set up and an initial migration applies cleanly against an empty
      database
- [ ] The module layout is feature-first, one module per area, with a single place that
      imports every model so migration autogeneration sees all tables
- [ ] A shared helper returns today's date in the configured business timezone; no other
      code computes the current date directly
- [ ] The OpenAPI document is served and imports into Postman without errors
- [ ] Responses are snake_case bare resources with the framework's default error shape;
      no success/data envelope
