# 42 — Notification records

**What to build:** Somewhere for the system to tell a user something, and for the user to
read it. The waitlist has to notify people when inventory is released, and without this
there is nothing for it to notify into.

Records the user polls, not email: SMTP means credentials, deliverability and an external
dependency the brief never asks for, and none of it can be demonstrated in Postman.

**Blocked by:** None — can start immediately

**Owner:** Time

**Status:** done — verified against a running app and a real database

- [x] A registered user lists their own notifications, newest first
- [x] Each notification carries a kind, a message, when it was created, and whether it has
      been read
- [x] A user marks a notification read
- [x] A user sees only their own; another user's reports not-found, exactly as bookings do
- [x] An unauthenticated caller is refused
- [x] A user with none receives an empty list rather than an error
- [x] Notifications are created by the system, never by a request: there is no route that
      lets a caller send one, to themselves or to anyone else
- [x] An admin does not receive or read other users' notifications through this route

## Hand-off note — unblocks nothing of Garfield's

This was the last ticket of mine with no blockers. His ticket 47 still waits on the waitlist
chain (43 to 46), none of which has started.

One thing for him when he reaches 47: **`_WIPE_ORDER` in `app/seed.py` gained `notifications`**,
first in the tuple. The fixture now also creates two notifications for the demo user, which is
what makes `GET /notifications` demonstrable at all.

## Notes

### What was built

`notifications` — user, kind, message, `created_at`, `read_at` — with exactly two routes:
`GET /notifications` and `POST /notifications/{id}/read`. Plus `notify()` in
`app/notifications/service.py`, which is the only thing that ever writes one.

### The absence of a create route is the feature

The criterion says notifications are created by the system, never by a request. That is
enforced by there being no route at all rather than by a guard on one, and verified from the
OpenAPI document rather than from reading the code:

```
every notification path in the OpenAPI document:
  ['/notifications', '/notifications/{notification_id}/read']
methods:
  [('/notifications', ['get']), ('/notifications/{notification_id}/read', ['post'])]

POST   /notifications      -> 405
PUT    /notifications      -> 405
POST   /notifications/1    -> 404
PATCH  /notifications/1    -> 404
DELETE /notifications/1    -> 404
```

If a client could post a notification it could post one to somebody else, and a record whose
provenance is "whoever asked" is not a record of anything.

### `notify()` flushes, and does not commit

This is the decision tickets 44 to 46 will lean on hardest, so it is worth stating plainly. A
notification is almost always part of something larger — a cancellation that frees a car both
deletes the booking and tells the next person in the queue — and those have to land together
or not at all. A `commit()` inside `notify()` would publish a notification about a transaction
that could still roll back, telling someone their car is ready when it is not.

Proved rather than assumed:

```
after notify(): id=3, visible in this session: 3
after rollback: 2
OK -- no notification escapes a failed transaction
```

The flush still assigns an id, so a caller can reference the notification it just created
within the same transaction.

### This is the first instant in the schema

Every other temporal column in this service is a plain `DATE`, deliberately: a rental has no
pickup hour, and storing an instant would invite a timezone conversion to shift the day. A
notification's creation is not a domain date but a record of a moment — rounding it to a day
would make two notifications from one afternoon indistinguishable and unorderable, and
ticket 43 needs exactly that ordering for the queue.

So `app/core/clock.py` gained **`now()`** beside `today()`, and its docstring now states which
is for what and why picking the wrong one is a bug in both directions. `datetime.now()`
elsewhere is a bug for precisely the reason `date.today()` is.

Instants are stored and returned in UTC, serialised as `2026-10-01T18:39:03.655622Z`. The
business timezone decides which *day* a rule thinks it is; it has no business re-rendering an
absolute moment, and converting would add ambiguity without adding information. Verified that
the stored value is timezone-aware — a naive datetime in a `timestamptz` column is read back
as whatever the session timezone happens to be, which is a silent off-by-seven-hours.

### `read_at`, not `is_read`

A nullable instant rather than a boolean. It answers strictly more — "has it been read" is
`read_at is not None`, exposed as a derived `is_read` property so one fact lives in one place
— and "when did they actually see this" is the question anyone debugging a missed notification
asks.

Marking read is **idempotent**: a second call answers 200 and leaves the original `read_at`
alone, because what it records is when the user *first* saw it and a retried request must not
rewrite that. There is no route to mark one unread; that would be a record of nothing.

A side benefit worth noting: idempotency is what lets `app/smoke.py` mark a seeded
notification read and still pass on a second run without re-seeding.

### The one place scope does not widen for an admin

Every other collection here shows an admin more — `GET /bookings` returns everyone's. This one
does not, and the contrast is deliberate: a booking is business the service may be asked to
account for, while a notification is addressed to a person. Reading other people's messages is
not oversight.

An admin calling `GET /notifications` gets their own, which in practice is `[]`, and reaching
for another user's by id answers 404 exactly as a registered user's attempt does. Both
verified. The alternative — 403 for an admin — was rejected because the system may one day
have something to tell an admin, and a route that refuses its own user is a worse lie than one
that returns nothing.

### Why the fixture had to grow

Nothing in the service emits a notification yet, by design: the waitlist is the first
producer. That left the ticket's own criteria unverifiable — "newest first", "marks one read"
and "whether it has been read" cannot be demonstrated against an empty table. This is the
narrow exception `CLAUDE.md` allows for something a criterion cannot be verified without, and
it is taken here loudly.

So `app/seed.py` creates two for the demo user, one read and one unread. Both describe facts
that are **actually true of the fixture** — the demo user really does hold an ended booking
awaiting a review, and really does hold one starting soon — rather than invented events. A
fixture that asserts something the rest of the fixture contradicts is worse than no fixture.

`NotificationKind` lists only `booking_confirmed` and `booking_ended`, the two that exist. The
waitlist's kinds are deliberately **not** pre-declared: a kind nothing emits reads as a
promise, and guessing at tickets 43 to 46's vocabulary before their code exists is how
interfaces end up with dead members.

### Verified

Against a running app and a real PostgreSQL:

```
list as demo                          -> 200, 2 rows, newest first
fields present                        -> created_at, id, is_read, kind, message, read_at
the read one carries read_at          -> true; the unread one is null/false
mark one read                         -> 200, is_read true, read_at set
mark it again                         -> 200, read_at unchanged
list as fresh (no notifications)      -> 200, [] -- a list, not an error
fresh marks demo's one read           -> 404
a notification that never existed     -> 404
an over-large id                      -> 422
list as admin                         -> 200, [] -- their own, not everyone's
admin marks demo's one read           -> 404
anonymous list / mark                 -> 401, 401
garbage token                         -> 401
```

In-process, through the only writer:

```
notify() then rollback                -> no notification survives
notify() then commit                  -> persists, created_at timezone-aware
delete the recipient user             -> notifications cascade, no orphan
```

Migration round-trips `upgrade` -> `downgrade base` -> `upgrade` with `alembic check`
reporting no drift. The seed runs. `app/smoke.py` gained fifteen checks: **139/139 passed,
twice with no re-seed between.**

The autogenerated migration created two indexes — one from `index=True` on `user_id` and the
composite `(user_id, created_at)`. The single-column one was dropped: a composite index
starting with `user_id` already serves a lookup by user alone, so the second was dead weight
on every insert.

### Left out

- **No `GET /notifications/{id}`** and no unread count. Neither is asked for, and a client
  holding the list needs neither.
- **No notification when a blackout window is scheduled over an existing booking**, which
  ticket 41 noted would be the natural first use of this table. It is a new rule rather than
  this ticket's surface, and emitting it here would have meant ticket 41's accepted cost
  quietly changing shape after the fact. Worth its own ticket if anyone wants it.
- **No deletion or expiry.** Notifications accumulate. Nothing asks for a retention rule, and
  inventing one would mean deciding how long a record of what someone was told is worth
  keeping — not a decision to make silently.
