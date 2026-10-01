# 50 — The provider nested in a booking always reports no reviews

**What to build:** A fix for a defect found while verifying ticket 25. `average_rating`
and `review_count` are correct when a provider is fetched as its own resource, but are
always `null` and `0` when the same provider appears **inside** a booking. A client
reading a booking is told, confidently and wrongly, that the provider has never been
reviewed.

**Blocked by:** None — can start immediately

**Owner:** Time

**Status:** done — verified against a running app and a real database

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

- [x] Decide between the two and record the reasoning in the ticket Notes
- [x] The same provider reports the same rating and count whether read directly or read
      inside a booking — or does not claim to report them at all
- [x] `GET /bookings` is checked as well as `GET /bookings/{id}`, since the list route
      builds its responses the same way
- [x] `docs/SPEC.md` says which shape a nested provider has, so the next person nesting
      a resource does not have to rediscover this

## Notes

Not fixed inside ticket 25, which found it: that ticket's job was to add a vehicle class
to a booking, and changing the shape of the nested provider is a separate behaviour
change that deserves its own commit and its own verification.

### Option 1, and why

**Nest a summary shape.** `ProviderSummary` carries the stored columns and nothing else;
`ProviderRead` extends it with the two aggregate fields and is built only by the provider
routes that run the aggregate.

Two reasons for removing the claim rather than filling it in:

- **A field that is sometimes a lie is worse than an absent one.** Populating the aggregate
  wherever a booking is built leaves the same trap set for the next person who nests
  something, and it would have to run in the booking *list* route once per row. The defect
  would be fixed in the two places anyone checked and waiting in the third.
- **A booking says who it is with and how to reach them.** What other people think of them is
  catalogue information — for *choosing* a provider, not for the record of a rental already
  made. `GET /providers` is where you choose, and it still carries both fields.

It is also the choice ticket 25 already made for the vehicle class, specifically to avoid
creating this bug a second time. Making the provider match means one rule instead of a
precedent and an exception.

### The cost, stated

The two fields **disappear** from the nested block. A client reading them there was reading a
falsehood, but it was a falsehood with a stable shape, so this is a visible change rather than
a silent repair. `docs/SPEC.md` now carries the rule and the reasoning under *What a nested
resource carries*.

### Verified

After leaving a review on the seeded ended booking, reproducing the original conditions:

```
GET /providers/5          -> average_rating=4.0  review_count=1
GET /bookings/3           -> provider keys: [address, id, is_retired, name, telephone]
                             no average_rating, no review_count
GET /bookings (owner)     -> all 2 carry the summary shape
GET /bookings (admin)     -> all 2 carry the summary shape
GET /providers            -> Fast Wheels: 4.0, 1 -- unchanged
```

The nested block still answers what a booking is for: `Fast Wheels, 021111111,
retired=False`.

The smoke run checks for the **absence** of the fields rather than for a correct value,
because a check for a correct value would pass again if someone reintroduced the default. It
also checks the catalogue still carries them, so the fix cannot go too far unnoticed. 182/182.

### A sibling of this defect, found and fixed in ticket 44

The same mistake in a different disguise: the waitlist response was built by naming fields one
at a time, so a newly added column silently took its default and every response reported
`offered_at: null` while the database held a timestamp. Fixed there by building the response
from the model's mapped columns by reflection. Worth knowing that this defect has now appeared
twice by two different routes — the shared cause is a response shape that can quietly default
a field nobody filled in.
