# 46 — An expired claim passes to the next in the queue

**What to build:** The requirement says the claim window comes "before offering it to the
next person in the queue", so expiry is not the end of the story — it hands on. This
closes the loop that makes a waitlist a queue rather than a lottery.

**Blocked by:** 45

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] An expired claim is offered to the next entry whose date range the capacity
      satisfies, and that person is notified
- [x] The expired holder loses their place rather than returning to the front
- [x] A declined claim passes on the same way as an expired one
- [x] When nobody is left in the queue, the capacity simply becomes available again
- [x] Passing on is evaluated lazily, when the queue is next touched, so a queue nobody
      reads for a week still behaves correctly when it is finally read
- [x] A chain works end to end: three people queue, the first lets the claim expire, the
      second declines, the third is offered it and books it
- [x] Time is judged in the business timezone, like every other rule
- [x] The whole pass-on happens under the same lock, so a claim cannot expire into two
      people's hands at once

## Hand-off note — GARFIELD IS NOW UNBLOCKED

**Both things ticket 47 waited on are done.** Ticket 41 landed blackout enforcement and this
closes the waitlist. The queue behaves correctly end to end, so a fixture can seed a waiting
one.

Three things he will want when he gets to 47:

- **`_WIPE_ORDER` in `app/seed.py` must list `waitlist_entries` and `notifications`** before
  the tables they point at. It does. Anything new of his that references an existing table
  with `RESTRICT` needs the same, or `python -m app.seed` dies — that has happened three
  times.
- **A seeded queue needs a full class.** Joining is refused unless the class is full for the
  dates, so the fixture has to book the class out first, exactly as a user would. Writing the
  entries straight through the ORM bypasses that check, which is fine for a fixture, but then
  the seeded state must still be one the API would have allowed or the demo contradicts the
  rules.
- **`CLAIM_WINDOW_MINUTES` is configuration**, default 60. Set it to 1 in the demo walkthrough
  if he wants a grader to watch a claim expire without waiting an hour.

## Notes

### Almost all of this ticket is the absence of code

That is worth saying plainly, because the diff is small and the behaviour is not.

An expired claim stops occupying a car **the moment it expires**, because occupancy asks "is
this claim live" rather than reading a stored flag. So capacity reappears on its own, with
nothing having run. Offering it to the next person is then the same operation as offering
capacity released by a cancellation — `offer_released_capacity` from ticket 44, unchanged.

Which means:

- *"A declined claim passes on the same way as an expired one"* needed nothing written. Both
  stop occupying; both make room; the same function offers it on.
- *"The expired holder loses their place rather than returning to the front"* needed nothing
  written. Their `offered_at` is set, so they can never be a candidate again.
- *"When nobody is left in the queue, the capacity simply becomes available"* needed nothing
  written. The offer loop finds no candidate and stops.

What this ticket actually adds is `settle_queue` — a loop around the existing offer — and four
places that call it.

### Lazy, and reads do the settling

There is no scheduler and this ticket does not add one. `GET /waitlist_entries` settles the
queues the caller is in before reporting their places; so do joining, converting, declining,
and deleting a booking.

**A GET with an effect is surprising, so it is documented rather than hidden.** Nothing is ever
*wrong* in the meantime — a claim past its expiry is never honoured, because liveness is
computed — the capacity it was holding has merely not been offered on yet.

Proved with a week-old lapse, checking the database directly before anyone looked:

```
a week later, before any read, has p2 been offered? f
p2's first read -> state=claimed
```

Only the queues the caller is in are settled. Settling every queue in the system on every read
would turn one person's list into a scan of the whole table.

### Why the loop

More than one claim can have lapsed since anyone looked. Each pass marks one entry, so the
loop shortens every time, and each offer re-reads occupancy — so the person just offered a car
immediately occupies it and the next pass sees the class full again. Exactly one offer per free
car, never two for one. That is also what makes the lock sufficient rather than merely
helpful.

### The chain, end to end

The criterion asked for three people, an expiry, a decline and a booking:

```
cancelled -> one: claimed, two: waiting, three: waiting
one's claim lapses (nothing runs; the expiry is simply backdated)
  before anyone looks, has two been offered? f
  two reads the queue -> state=claimed position=1, notified waitlist_offer
  one: expired -- lost their place, not returned to the front
  three: waiting, position 2
two declines
  three -> claimed, position 1, notified waitlist_offer
three books it
  POST .../claim -> 201
```

### Two reads cannot pass one claim to two people

Fired two reads of the same stale queue at the same instant:

```
two reads fired at once -> [200, 200]; live claims on the class now: 1
r2=claimed  r3=waiting
```

Exactly one live claim, held by the person who was next. Without the lock both readers would
have found the same lapsed claim and the same next person.

### A case worth having tested: joining settles too

A class whose front claim lapsed days ago has a free car. Joining its queue must therefore be
**refused** — "not full, book it instead" — and that is only right if the stale hold was
noticed first:

```
joining a class whose stale hold just lapsed -> 409 "... is not full between ..."
```

Without settling on join, the caller would have been given a queue place for a car they could
simply have booked.

### Verified

```
the full chain: expire, decline, book                -> as above
nobody left in the queue                             -> capacity available, outsider books it
a week unread, then one read                         -> settles correctly
joining a class whose hold just lapsed               -> 409 not full
two simultaneous reads of a stale queue              -> exactly one live claim
```

Migration: none needed — this ticket adds no columns, which is itself the point. `alembic
check` clean, the seed runs, **180/180 smoke checks**, twice with no re-seed between.

One thing the smoke run surfaced: converted and declined entries stay in the table by design,
and they hold a `RESTRICT` key to their class, so a teardown that removes a test class has to
clear them first — each by the person who owns it, since there is deliberately no admin route
into a queue.

### Requirement 4 is now complete

Join a waitlist for a fully-booked class, strict FIFO release on cancellation, notification, a
time-limited exclusive claim, and pass-on to the next person. All five clauses built and
verified.

