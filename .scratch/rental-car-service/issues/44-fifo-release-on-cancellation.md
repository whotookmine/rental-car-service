# 44 — Released inventory goes to the queue in order

**What to build:** When a cancellation frees a vehicle, the person who has waited longest
for it gets it. The requirement says strict FIFO, so the order must be the order of joining
and nothing else — not who is quickest to notice, and not who asks first.

**Blocked by:** 43, 41

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] Deleting a booking that leaves a class no longer full offers the freed capacity to
      the first waitlist entry whose date range it satisfies
- [x] The order is strictly the order of joining, verified with at least three people in
      one queue
- [x] An entry whose range the freed capacity does not cover is skipped without losing its
      place for a future release
- [x] A release that frees capacity no entry wants leaves the queue untouched
- [x] Two cancellations in quick succession offer to the first and second in the queue
      respectively, never both to the first
- [x] The offer is made under the same lock as the capacity count, so two simultaneous
      cancellations cannot both offer the same vehicle to the same person
- [x] Nothing is booked automatically: an offer is an opportunity, and ticket 45 governs
      how it is taken

## Notes

### What changed

One column, `waitlist_entries.offered_at`, one function, `offer_released_capacity`, and
eight lines in `delete_booking`.

### "Whose date range the freed capacity satisfies" — answered, not guessed

The tempting implementation compares the cancelled booking's range against each entry's
range. It is also wrong: whether a release helps someone depends on every *other* booking
over their range, not just the one that went.

So the question is put to `measure_room` — the function booking, availability and joining all
share. If the class is no longer full over the range someone wants, the release is usable by
them. That cannot disagree with what booking will do when they try, because it is the same
question.

The difference is observable. One car, two consecutive bookings, A waiting for the whole span
and B for only the later half:

```
a wants 2026-12-11..2026-12-16 (joined first); b wants 2026-12-14..2026-12-16
cancelled the 2026-12-14..2026-12-16 booking
  a offered=False   <- a's span is still blocked by the other booking
  b offered=True    <- b takes it, despite joining later
a is still at position 1 in its own queue, unmarked
after cancelling the other booking too: a offered=True
```

A range-comparison implementation would have offered it to A, who could not have used it.

### Skipping costs nothing, because candidacy is computed

An entry the release cannot satisfy is not marked, not moved and not recorded as passed over.
The next release simply considers it again. "Without losing its place" is therefore not a
feature with code behind it — it is what happens when you compute candidacy instead of
storing it.

### `offered_at` is what takes someone out of contention

This is the whole mechanism behind "two cancellations offer to the first and second, never
both to the first":

```
2 cars, both booked, 3 waiting
after the first cancellation:  offered = [True, False, False]
after the second cancellation: offered = [True, True, False]
```

### The lock, and why it is taken before the delete

Deleting and then offering is two steps over one piece of state, so the vehicle class row is
locked **before** the delete and held across both. Without it, two simultaneous cancellations
would both read the same queue, both find the same person at the front, and both offer them
the capacity — one car promised twice, and the second person in the queue never hearing
anything.

Fired at the same instant:

```
both cancellations fired at once -> [204, 204]
p1 offered=True  p2 offered=True
two releases reached two different people
```

The delete is flushed rather than committed, so the offer measures a world where the booking
is already gone, and both land together or not at all. A commit in between would leave a
window where the car is free and nobody has been told.

### A defect this ticket introduced and this ticket's own test caught

Adding `offered_at` to the model and the schema was not enough: the waitlist response was
built by naming fields one at a time, so the new field silently took its default and **every
response reported `offered_at: null` while the database held a timestamp.**

That is exactly ticket 50's defect — a field that is sometimes a lie — reached by the same
route. The fix was not to add the missing line but to remove the possibility: the response is
now assembled by reflecting over the model's mapped columns, with the two computed fields
layered on top. Adding a column can no longer quietly fail to appear.

Found because the test knew what the answer should be and the database disagreed with the
API. A test that only checked for a 204 would have passed.

### Verified

```
three queue at 1, 2, 3; cancel -> only the first is offered
the offer creates no booking                     -> a's bookings []
two cancellations in succession                  -> first, then second
a release the first cannot use                   -> skipped, place kept, later release reaches them
a release nobody can use                         -> every entry untouched
then the matching cancellation                   -> offered
an inert (aged-out) entry                        -> never offered
two simultaneous cancellations                   -> two different people offered
```

Migration round-trips, `alembic check` clean, the seed runs, **166/166 smoke checks** twice
with no re-seed between.

### Left out

Still no claim, no expiry, no notification and no conversion. An offer is at this point only a
timestamp saying "you are next" — ticket 45 gives it a deadline, tells the holder through
ticket 42, and holds the capacity against everyone else.
