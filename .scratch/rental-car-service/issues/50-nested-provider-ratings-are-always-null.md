# 50 — The provider nested in a booking always reports no reviews

**What to build:** A fix for a defect found while verifying ticket 25. `average_rating`
and `review_count` are correct when a provider is fetched as its own resource, but are
always `null` and `0` when the same provider appears **inside** a booking. A client
reading a booking is told, confidently and wrongly, that the provider has never been
reviewed.

**Blocked by:** None — can start immediately

**Owner:** Time

**Status:** ready-for-agent

## How it happens

`BookingRead` nests the full `ProviderRead`. Those two fields are not columns; they are
produced by an aggregate query that only the provider routes run. Validating the shape
straight from a `Provider` object finds no such attributes and falls back to the field
defaults — so the booking reports an absence of reviews rather than an absence of data.

Reproduced on 2026-09-24 against the seeded database, after leaving one review on the
demo user's ended booking:

```
GET /providers/1   -> "average_rating": 4.0,  "review_count": 1
GET /bookings/1    -> "provider": { ... "average_rating": null, "review_count": 0 }
```

Same provider, same request second, two different answers.

## Two ways to fix it, pick one and say why

1. **Nest a summary shape** that carries only the stored columns, the way ticket 25
   nested `VehicleClassSummary` instead of `VehicleClassRead` to avoid creating this
   exact bug a second time. A field that is absent is honest; a field that is sometimes
   a lie is not.
2. **Populate the aggregate** wherever a booking is returned, so the nested block is as
   correct as the standalone one. More useful to a client, but it puts the ratings query
   into the booking list route, where it runs for every row.

- [ ] Decide between the two and record the reasoning in the ticket Notes
- [ ] The same provider reports the same rating and count whether read directly or read
      inside a booking — or does not claim to report them at all
- [ ] `GET /bookings` is checked as well as `GET /bookings/{id}`, since the list route
      builds its responses the same way
- [ ] `docs/SPEC.md` says which shape a nested provider has, so the next person nesting
      a resource does not have to rediscover this

## Notes

Not fixed inside ticket 25, which found it: that ticket's job was to add a vehicle class
to a booking, and changing the shape of the nested provider is a separate behaviour
change that deserves its own commit and its own verification.
