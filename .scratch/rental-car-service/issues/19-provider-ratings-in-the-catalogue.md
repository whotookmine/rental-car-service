# 19 — Provider ratings in the catalogue

**What to build:** The provider list shows how each provider has been rated and how many
people rated it, so a registered user can tell a well-regarded provider from an untested one.
Figures are aggregated on read and never stored: stored counters would drift silently,
because the booking-to-review cascade fires inside the database and would bypass any
application-level counter update.

**Blocked by:** 15

**Owner:** Garfield

**Status:** done

- [x] Every entry in the provider list carries an average rating and a review count
- [x] Fetching a single provider carries the same two figures
- [x] A provider with no reviews reports no rating rather than zero, so that an untested
      provider is not mistaken for a terrible one, and a review count of zero
- [x] Averages are rounded to one decimal place in responses and held at full precision in
      storage
- [x] The figures are computed by aggregation at read time; no average or count is stored
      on the provider
- [x] Adding, editing, or deleting a review moves the figures
- [x] Deleting a booking that carried a review moves the figures
- [x] Retired providers keep their figures, visible when fetched by identifier
- [x] The list is served by a single query rather than one query per provider

## Notes

`ProviderRead` schema gains `average_rating: float | None` and `review_count: int`.
All 6 provider routes now return these fields.

The list uses a single LEFT JOIN subquery through bookings → reviews, GROUP BY provider.id.
`_fetch_one()` reuses the same subquery pattern for single-provider routes.

`ORDER BY name, id` added to list — fixes the flaky order noted in ticket 08 and required
by ticket 22's Postman assertions.

SQL ROUND applied to AVG cast to Numeric for correct decimal rounding in PostgreSQL.
Python converts the Decimal result to float for the response.

`docs/SPEC.md` updated to describe the aggregation approach and null semantics.

## Note from ticket 08

`GET /providers` currently has no `ORDER BY`, so rows come back in whatever order
PostgreSQL returns them, and that order visibly changes between runs. This ticket rebuilds
that query to add the rating aggregate, so it is the natural place to give the list a
stable order. Without one, ticket 22's Postman assertions on list contents will be flaky.

