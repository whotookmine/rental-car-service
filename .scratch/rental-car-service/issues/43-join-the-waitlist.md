# 43 — Joining the waitlist

**What to build:** When a class is full for the dates someone wants, they can queue for it
instead of simply being refused. The queue is per provider, class and date range, and its
order is the order people joined — that ordering is what ticket 44 depends on.

**Blocked by:** 26

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] A registered user joins the waitlist for a provider, vehicle class and date range
- [x] Joining is refused when the class is **not** full for those dates, since they should
      simply book it
- [x] A user may not join the same queue twice; the second attempt is a conflict
- [x] A user sees their own waitlist entries and where they stand in the queue
- [x] A user leaves a waitlist, and doing so closes the gap for everyone behind them
- [x] Entries record the moment of joining, precisely enough that two entries made close
      together still have a definite order
- [x] Another user's entry reports not-found, matching bookings
- [x] The same date rules apply as booking: end on or after start, at most thirty days, no
      past-dated ranges
- [x] Waitlist entries for a date range that has passed are inert and never offered

## Notes

### What was built

`waitlist_entries` and three routes: `POST /providers/{id}/waitlist_entries`,
`GET /waitlist_entries`, `DELETE /waitlist_entries/{id}`.

### One home for "full", because two copies already disagreed once

Joining is refused unless the class really is full, which means asking the same question
booking asks. Rather than write that arithmetic a third time, I extracted it: `measure_room`
in `app/bookings/rules.py` returns a `ClassRoom` of total, blacked-out, available and peak
bookings, and `ensure_class_has_room`, availability and the waitlist all read it.

Ticket 40 is why this mattered enough to refactor: availability and booking computed the same
thing in two places and immediately disagreed, and ticket 41 had to close the gap. A third
copy would have been a third chance to drift.

### Position is counted, never stored

A stored position would have to be rewritten for everyone behind anyone who leaves, and the
first missed update leaves two people believing they are third. Counting from join order
cannot drift, and makes "leaving closes the gap" free rather than a feature:

```
a, b, c join           -> positions 1, 2, 3
a leaves (204)
b and c read their own -> positions 1, 2
```

Order is `created_at` then `id`. The tiebreak is not decoration: two entries written in the
same microsecond would otherwise come back in whatever order PostgreSQL liked, and for a
queue whose entire promise is strict FIFO that would be a silent lottery. Ticket 44 depends
on this ordering being total.

### A queue is a provider, a class and an *exact* range

Capacity released for the 10th to the 12th is not capacity for the 9th to the 15th, so those
are different queues. This is what the requirement describes, and it also makes "inert"
simple: a whole queue ages out together, because the range is part of its identity. An entry
whose range has passed stays visible as the holder's own record with `is_active: false`.

Verified by inserting an aged-out entry directly — the API refuses past ranges, as it should,
so a fixture-style bypass is the only way to observe one:

```
b's entries: [('2026-09-11','2026-09-21', pos 1, active False),
              ('2026-12-01','2026-12-02', pos 1, active True)]
```

### Two wording defects my own verification caught

Neither was in this ticket's new code, and both would have reached a grader:

- **`require_registered_user` said "Admins do not hold bookings."** Exactly right while
  bookings were the only thing it guarded; an admin refused from a *queue* was being told
  something about bookings. The message now states the rule rather than one instance of it:
  *"Admins manage rentals rather than holding them, so they cannot book or join a waitlist."*
  `docs/SPEC.md` and `docs/REQUIREMENTS-TRACE.md` updated in the same commit, since the old
  string was quoted in both.
- **"1 of its vehicles are still free."** Pluralised properly.

### Deliberately absent

- **No route lists a whole queue**, and none shows another person's place. Who else is waiting
  is not the caller's business; their own position is all they need, and publishing the queue
  would let anyone measure a provider's demand.
- **No admin oversight of queues.** Nothing in the requirement asks for it, and narrow scope
  means the ordering rules have one code path rather than two. An admin reaching for an entry
  gets 404, like anyone else.
- **No cap on how many queues one person may join.** The active-booking cap exists because a
  booking holds a car; a waitlist place holds nothing.
- **No claim, no offer, no notification.** Joining a queue does nothing yet when capacity
  frees — that is ticket 44, and it is why this entry carries a precise `created_at`.

### Verified

```
join while a car is free                 -> 409 naming how many are free
fill the class, then three users join    -> 201, positions 1, 2, 3
the same user joins again                -> 409
the first leaves, others move up         -> 204, then positions 1, 2
another user's entry / an admin's reach   -> 404, 404
an entry that never existed / over-large -> 404, 422
end before start / over 30 days / past   -> 422, 422, 422
a class that does not exist              -> 422
an unexpected field                      -> 422
an admin joins                           -> 403
anonymous joins / lists                  -> 401, 401
another provider's class                 -> 409
a retired provider                       -> 409
a user in no queue                       -> 200, []
an aged-out entry                        -> visible, is_active False
```

Migration round-trips with `alembic check` clean; the seed runs; `app/smoke.py` gained
twenty-two waitlist checks — **164/164 passed, twice with no re-seed between**.

Two bugs in my own smoke additions, worth recording because both are easy to repeat:
borrowing an existing throwaway user who was already at the three-active cap, and guarding a
response with `isinstance(x, dict)` when a 409 error body is also a dict — which walked
straight into a `KeyError`. The run's own crash guard caught the second and still printed a
summary rather than dying halfway.
