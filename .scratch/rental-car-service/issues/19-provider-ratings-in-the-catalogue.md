# 19 — Provider ratings in the catalogue

**What to build:** The provider list shows how each provider has been rated and how many
people rated it, so a customer can tell a well-regarded provider from an untested one.
Figures are aggregated on read and never stored: stored counters would drift silently,
because the booking-to-review cascade fires inside the database and would bypass any
application-level counter update.

**Blocked by:** 15

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] Every entry in the provider list carries an average rating and a review count
- [ ] Fetching a single provider carries the same two figures
- [ ] A provider with no reviews reports no rating rather than zero, so that an untested
      provider is not mistaken for a terrible one, and a review count of zero
- [ ] Averages are rounded to one decimal place in responses and held at full precision in
      storage
- [ ] The figures are computed by aggregation at read time; no average or count is stored
      on the provider
- [ ] Adding, editing, or deleting a review moves the figures
- [ ] Deleting a booking that carried a review moves the figures
- [ ] Retired providers keep their figures, visible when fetched by identifier
- [ ] The list is served by a single query rather than one query per provider

## Note from ticket 08

`GET /providers` currently has no `ORDER BY`, so rows come back in whatever order
PostgreSQL returns them, and that order visibly changes between runs. This ticket rebuilds
that query to add the rating aggregate, so it is the natural place to give the list a
stable order. Without one, ticket 22's Postman assertions on list contents will be flaky.

