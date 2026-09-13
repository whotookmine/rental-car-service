# 01 — Project scaffold and health check

**What to build:** The service starts, reads its configuration from the environment,
connects to PostgreSQL, and answers a health check. The database schema is reproducible
from empty by running migrations, and the API's OpenAPI document can be imported into
Postman as a working collection. Also lands the shared helper that every later date rule
depends on: the current date computed in the configured business timezone, never from the
system clock directly.

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] The application starts and serves over HTTP
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
