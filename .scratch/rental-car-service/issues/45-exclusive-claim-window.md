# 45 — The exclusive claim window

**What to build:** When capacity is offered to someone on the waitlist, it is held for them
alone for a limited time. The requirement calls it a time-limited exclusive claim, so two
things must both be true: nobody else can take it during the window, and it does not last
forever.

**Blocked by:** 44, 42

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] An offer creates a claim with an expiry, and the holder is notified through ticket 42
- [x] The claim's duration is configuration, not a hardcoded number, and is stated in
      `docs/SPEC.md`
- [x] While a claim is live, the vehicle it holds is not available to anyone else: another
      user booking that class for those dates is refused as full, even though a vehicle is
      physically free
- [x] The claim holder converts it into a booking, which succeeds despite the class
      appearing full to everyone else
- [x] Converting a claim consumes it; the same claim cannot be used twice
- [x] The holder may decline, which releases the capacity immediately rather than waiting
      for expiry
- [x] A claim belonging to another user reports not-found
- [x] Expiry is judged when the queue is next read or written, not by a background job:
      there is no scheduler in this project, and a claim that has passed its expiry must
      never be honoured even if nothing has touched the queue since

## Notes

### What was built

Four columns on a waitlist entry — `claim_expires_at`, `converted_at`,
`converted_booking_id`, `declined_at` — a configurable window, two routes, and one change to
how occupancy is counted.

### The central decision: a live claim occupies a car exactly as a booking does

"Nobody else can take it during the window" could have been a special case bolted onto the
booking route. Instead a live claim is counted in the same per-day occupancy figure as a
booking, so the class simply **is** full while a claim stands. Every reader of fullness — the
booking refusal, availability, and joining the queue — gets the right answer without knowing
claims exist.

The holder's own claim is excluded when they convert it. Without that they would be refused
by the very reservation made for them, which is the one thing an exclusive claim must never
do.

```
claim live:  availability 0, outsider books -> 409, next-in-queue books -> 409
the holder:  POST .../claim -> 201 with the booking
```

### Both occupancy queries had to change, and they are separate SQL

`_PEAK_OCCUPANCY_ON_ANY_DAY` in `app/bookings/rules.py` and `_AVAILABILITY_QUERY` in
`app/providers/router.py` are deliberately separate, because ticket 27 asked for availability
to be one query rather than one per class and that is worth keeping. It does mean a change to
either is a change to both.

Rather than trust that, the agreement is tested: a class whose only free car is held by a
claim reports `free_count: 0` **and** refuses a booking, and after the claim is declined
reports 1 and accepts one. Ticket 40 is why this is not left to inspection.

Both queries take the measuring instant as a parameter rather than calling `now()` inside the
SQL, so one request measures every claim against one moment. A query reading the clock per row
could count the same claim as live and dead within a single answer.

### Expiry without a scheduler

There is no background job in this project and this ticket does not add one. Claim state is
derived from the timestamps every time it is asked for, so a claim that lapsed overnight is
simply not live the next time anyone touches the queue.

Verified by backdating an expiry — nothing ran, nothing was marked:

```
after backdating the expiry: state=expired (nothing ran to mark it)
availability is now 1 -- the hold is gone
converting an expired claim -> 409 "The claim ... has expired"
```

**State is derived, never stored.** A stored state and the timestamps behind it are two facts
that can disagree, and the disagreement is always found later than it was caused. It is also
what makes lazy expiry work at all: there is nothing to forget to update.

### The window is configuration

`CLAIM_WINDOW_MINUTES`, default 60, `gt=0`. Proved by running the app with `5` and measuring
the gap between `offered_at` and `claim_expires_at`:

```
with CLAIM_WINDOW_MINUTES=5 the window is 5 minutes
CLAIM_WINDOW_MINUTES=0 -> refused at startup: "Input should be greater than 0"
```

Zero is refused because such a claim would expire in the instant it was created: the offer
could never be taken, and the queue would quietly drain itself.

### Declining is a decision; expiry is the absence of one

Both end a claim, but declining releases the car **immediately** rather than making everyone
behind wait out the window. They are separate columns because they are separate facts, and
ticket 46 passes both on the same way.

```
c declines -> 200 state=declined
availability immediately after declining: 1
```

### Converting is not an exemption from the rules about holding a car

A conversion goes through the provider-retired check, branch resolution, the one-way rule and
the owner's three-active cap. A claim offers a car; it does not make someone allowed to hold
four. The class and dates come from the entry rather than the body, because the car is held
for *those* days — claiming it for others would be a new request, not taking the offer.

### Position had to change too

Once an entry could be converted, declined or expired, counting those ahead of someone would
have told the person behind a converted entry that they were still second when they were next.
Position now counts only entries still in contention. Not in this ticket's criteria, but it is
this ticket that made the old behaviour wrong.

### Two defects found while building this

- **The autogenerated migration emitted an unnamed foreign key** and a matching
  `drop_constraint(None, ...)`. That downgrade cannot work — PostgreSQL has no way to drop a
  constraint you cannot name — so `alembic downgrade` would have failed the first time anyone
  ran it, which is exactly the check `CLAUDE.md` asks for on every ticket. Named in both the
  migration and the model, so a future autogenerate will not reintroduce it. Verified by a
  single-step down and up, not just a full rebuild.
- **`peak_bookings` was a lie once claims were counted.** Renamed to `peak_occupancy`
  throughout.

### A lock-order exception, recorded rather than hidden

A conversion holds the vehicle class row and then takes the owner row inside
`ensure_room_for_another_booking` — the **reverse** of the order every other path uses. It is
safe only because that route takes no further locks afterwards, and because no other path
holds an owner row while reaching for a class row. `docs/SPEC.md` names this as the route to
revisit if a future ticket adds one.

### Verified

```
an offer creates a claim with an expiry           -> state=claimed, 60 minutes from config
the holder is notified                            -> one waitlist_offer notification
the next person in the queue is told nothing      -> []
availability while the claim is live              -> 0, though a car is free
an outsider / the next in queue books it          -> 409, 409
the holder converts                               -> 201, the right class and dates
the same claim again                              -> 409 "only be taken once"
the person behind moves to position 1             -> waiting, position 1
declining                                         -> 200, availability 1 at once
declining again                                   -> 409
a backdated expiry                                -> state=expired, hold released, 409 to convert
claiming when nothing was offered                 -> 409 "still in the queue"
another user's entry / an admin's / anonymous     -> 404, 404, 401
an unexpected field                               -> 422
a branch that does not exist / another provider's -> 422, 409
```

Migration round-trips both ways with `alembic check` clean; the seed runs; **174/174 smoke
checks**, twice with no re-seed between.

### Left out

Nothing happens to the queue when a claim expires or is declined: the capacity is released to
everyone rather than offered to the next person waiting. That is ticket 46, and it is the last
clause of requirement 4.
