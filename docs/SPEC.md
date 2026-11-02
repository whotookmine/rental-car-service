# Rental Car Service — Agreed Design

Terminology is defined in [CONTEXT.md](../CONTEXT.md). Decisions with lasting
consequences are recorded in [docs/adr](./adr). This file is the working specification:
the rules, the surface, and the shape of the system as agreed.

This is the design we agreed, not the brief we were handed. The requirements as given live
verbatim in [REQUIREMENTS-TRACE.md](./REQUIREMENTS-TRACE.md), mapped clause by clause to
what satisfies them — read that one when the question is *"does this meet the
requirements?"* rather than *"how does this behave?"*

## Stack

Python, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic, PostgreSQL. Feature-first layout
(`auth/`, `bookings/`, `providers/`, `reviews/`, `vehicle_classes/`, `vehicles/`), with a
single `app/db/base.py` that imports every model so Alembic autogeneration sees all
tables. JSON is snake_case, bare
resources, FastAPI's default `{"detail": ...}` error shape with self-explaining messages.

## Entities

There was no Car entity in the first round of work: a booking reserved a period with a
provider and nothing else. The second round introduces the **vehicle class** — the kind
of car a provider rents — because a waitlist has to queue for something more specific
than a whole business. Since ticket 25 a booking names one.

- **User** — name, telephone, email (unique, lowercased), password hash, role
  (`user` | `admin`, defaults to `user`, never settable through the API).
- **Provider** — name, address, telephone, `is_retired`.
- **Vehicle Class** — provider, name, description. The kind of car, not an individual
  car. Belongs to exactly one provider for its whole life.
- **Vehicle** — vehicle class, plate (unique system-wide). One individual car.
- **Booking** — user, provider, vehicle class, `start_date`, `end_date` (both `DATE`).
- **Blackout Window** — vehicle, `start_date`, `end_date` (both `DATE`, inclusive). A
  period one car is off the road for servicing. No two on one vehicle may overlap.
- **Notification** — user, kind, message, `created_at`, `read_at` (nullable). A record the
  system writes for one user to read.
- **Waitlist Entry** — user, provider, vehicle class, `start_date`, `end_date`, `created_at`.
  One person's place in one queue. `created_at` is an instant because its order *is* the
  queue's order.
- **Review** — booking (unique), rating 1–5, comment.

## Dates

Dates are `DATE` columns with no time
 component. "Today" is computed in the configured
business timezone (`BUSINESS_TIMEZONE`, `Asia/Bangkok`) via a single `today()` helper.
No rule may call `date.today()` directly.

### Dates versus instants

Every domain period in this service is a plain `DATE`: rental periods, blackout windows, and
every rule that compares against "now". A rental has no pickup hour, and storing an instant
would invite a timezone conversion to shift the day.

**Two things are exceptions.** When a notification was created and when it was read are
records of a moment, not domain dates — rounding them to a day would make two notifications
from one afternoon indistinguishable. And a waitlist entry's `created_at` *is* the queue's
FIFO order, so it must distinguish two people who joined seconds apart. Both are
`timestamptz`. A waitlist entry's wanted range stays a pair of plain dates, because that is
a domain period like any other.

`app/core/clock.py` owns both: `today()` for a domain date, `now()` for an instant. Calling
`date.today()` or `datetime.now()` anywhere else is a bug, for the same reason in both cases —
the system clock's timezone is not the business timezone, and the service runs seven hours
from UTC.

Instants are stored and returned in UTC, serialised as ISO-8601 with a `Z`
(`2026-10-01T18:39:03.655622Z`). The business timezone governs which *day* a rule thinks it
is, not how an absolute moment is rendered; converting the rendering would add ambiguity
without adding information.

One module is exempt and says so: access tokens read UTC directly, because a JWT's `iat` and
`exp` are defined by the standard as seconds since the Unix epoch. A token's lifetime is not a
domain rule and has no business day.

## Rules

### Bookings

- `end_date >= start_date`.
- Rental period is at most 30 days.
- `start_date` must not be in the past **on creation**. Updates may touch past dates, so
  that a booking already underway can be extended and an admin can correct history.
- A registered user may hold at most 3 **active** bookings (rental period not yet ended).
  Deleting a booking frees a slot immediately. The check locks the owner's row before
  counting, so two simultaneous requests cannot both see a free slot and both take it —
  this is the transaction ADR 0001 cited when choosing PostgreSQL.
- A booking names one of that provider's vehicle classes, required at creation. A class
  that does not exist answers 422 — it is a bad value in the body, not a missing resource
  at the path — and a class belonging to a different provider answers 409, naming both so
  the caller knows which half of the request to change. The class is resolved before the
  active-booking cap is taken, so a request with the wrong class is told what is actually
  wrong with it.
- A booking names a pickup branch, required at creation. The same two-refusal logic
  applies: a branch that does not exist answers 422; one that belongs to a different
  provider answers 409. The branch is fixed at creation for the same reason as the vehicle
  class — it records where the car was collected — and sending `pickup_branch_id` when
  re-dating is refused with 422. The pickup branch is nested in every booking response.
- A booking may also name a drop-off branch (`dropoff_branch_id`), which is optional.
  Omitting it means returning to the pickup branch (the ordinary round-trip case).
  When a drop-off branch is named and it differs from the pickup branch, the provider
  must have enabled one-way service from the pickup to the drop-off branch; if it has not,
  the request is refused with 409 naming the two branches. Sending the same id for both
  pickup and drop-off is treated as a round-trip (null stored). The drop-off branch is
  fixed at creation and appears nested in the booking response (null for round-trips).
  A drop-off branch belonging to a different provider answers 409, exactly as the pickup
  branch does. ON DELETE RESTRICT, so a branch named by a one-way booking cannot be
  removed without first removing or re-pointing those bookings.
- The vehicle class is fixed at creation, exactly as the provider is, and for the same
  reason: a review must keep describing what was actually rented. Sending either when
  re-dating is refused with 422, never ignored.
- A booking cannot be created against a retired provider (409). Existing bookings made
  before retirement are unaffected and remain viewable. Reinstating the provider makes it
  bookable again.
- Overlapping bookings by the same user are allowed. The active cap bounds abuse, and a
  class's capacity bounds the rest: a user may hold two bookings at once so long as the
  class has room for both.
- **A vehicle class is booked at most as many times on any one day as it has vehicles on
  the road.** The check is per day, not per booking: two bookings sharing even one day both
  consume a car that day, so a whole-period comparison would let a class be over-booked by
  bookings that merely fail to nest. The busiest day in the requested period is compared
  against the cars available for that period, and a peak at or above it is refused with 409
  naming the class and the dates. Adjacent periods do not conflict — a booking ending on the
  10th and one starting on the 11th share no day.
- **Cars available = cars in the class − cars off the road for maintenance for any day of
  the period.** Since ticket 41 all three counts meet in one comparison, so two vehicles with
  one blacked out and one already booked is a full class even though neither count alone
  reaches two. A car blacked out for a single day of the period is out for the whole period:
  a car you would have to hand back to the workshop midway through is not a car you can rent
  for the period. This is the arithmetic `GET /providers/{id}/availability` performs, which
  is what makes the two agree rather than merely tend to.
- **The refusal says which shortfall it is**, because the remedy differs and a caller cannot
  guess:
  - no vehicles at all — *"it has no vehicles"*; nothing to wait for
  - every car in the workshop — *"off the road for maintenance … Waiting will not free one,
    because no other booking is holding them; try different dates"*
  - fully booked — the class's cars are *"taken on at least one of those days"*; a
    cancellation does free one, which is what the waitlist in ticket 43 will queue for
  - both — *"N of its M vehicles are off the road for maintenance … and the K still on the
    road are taken"*, so the caller knows part of the shortfall will never be released
    however long they wait
  The word *unavailable* is deliberately not used: `CONTEXT.md` forbids it under **Fully
  Booked**, precisely so that the two situations cannot be blurred into one sentence.
- A class with no vehicles refuses every booking, and says so rather than reporting a
  generic conflict.
- The capacity check applies to re-dating as well as creation, for owners and admins
  alike, measured against the booking's own class and excluding the booking itself, which
  is moving rather than being added. Unlike the active-booking cap it is checked whatever
  the new dates are, including ones wholly in the past: a past-dated booking still
  occupied a car on those days, and an admin correcting history must not be able to record
  four rentals of a class that only ever had three cars.
- Capacity frees the moment a booking is deleted, exactly as a user's own slot does.
- Selling cars can leave a class holding more bookings than it has capacity for. Those
  bookings stand — history is never destroyed to satisfy a later rule — and only new ones
  are refused.
- The count is taken under a row lock on the vehicle class, for the reason the active cap
  locks the owner: counting and then inserting is a race, and two requests could otherwise
  both see the last car free and both take it. **Scheduling a blackout window locks that same
  row**, so a booking and a maintenance window cannot race either — one waits for the other
  to commit and then counts what it did. A booking cannot lock the vehicle instead: it names
  a class, not a car, and has no way to know which vehicle to lock. **Lock order is owner,
  then vehicle class, then vehicle, on every path that takes more than one.** Two routes
  taking them in opposite orders is how a deadlock is built.
- The caller's own cap is checked before the class's capacity. It is the limit they
  control entirely, and checking it first skips the per-day query for a request that would
  fail regardless.
- Only the dates are mutable, for owner and admin alike. The provider is fixed at
  creation.
- Every edit is validated identically whether the owner or an admin makes it: date
  ordering, the 30-day maximum, and the 3-active cap, the last measured against the
  booking's owner. Admins have wider scope, not weaker rules, and share the same code
  path. The accepted cost is that an admin cannot extend an ended booking for a user who
  already holds 3 active ones, even to correct a genuine error.
- The cap is re-checked on an edit **only when the new dates would leave the booking
  active**, and the booking being edited is excluded from its own count. An owner at the
  cap can therefore still re-date their bookings, and can still edit an ended booking that
  stays ended, since it occupies no slot; what they cannot do is extend an ended booking
  into the future to gain a fourth active one.
- The refusal names whoever is actually at the limit: an owner is addressed directly, and
  an admin editing someone else's booking is told about that booking's owner.
- A booking that has a review cannot be edited such that its rental period would no
  longer be ended (409). This applies to owners and admins alike; it keeps every review
  in the table attached to a finished rental. "No longer ended" uses the same boundary as
  the active-booking cap, so moving a reviewed booking to end **today** is refused just as
  moving it into the future is.
- When an edit breaks both this rule and the cap, the review refusal is the one reported.
  It is absolute — no amount of freeing slots makes a reviewed booking movable into the
  future — whereas the cap clears on its own as rental periods end. Malformed dates still
  answer 422 ahead of either, since validation runs before the handler.
- Admins do not hold bookings or waitlist places. `POST /providers/{id}/bookings` refuses an admin caller
  with 403. The cap is a rule about a renter's behaviour and admin oversight is defined as
  acting on other people's bookings; an admin holding their own would make both ambiguous.

### Reviews

- One review per booking, enforced by a unique constraint.
- Creatable only once the booking's rental period has ended, and only by the booking's
  owner.
- Rating and comment are mutable by the owner; the booking it belongs to is not.
- Deleting a booking cascades to its review at the database level. Deleting a review
  leaves the booking intact and reviewable again.
- A retired provider is still reviewable by users who booked it.

### Notifications

- A notification is a record the system writes for **one** user, who lists their own and
  marks them read. Records the user polls, not email: SMTP would mean credentials,
  deliverability and an external dependency the brief never asks for, and none of it can be
  shown in Postman, which is this project's only demonstration.
- **No route creates one.** This is a rule, not an omission. If a client could post a
  notification it could post one to another user, and a record whose provenance is "whoever
  asked" is not a record of anything. The only writer is `notify()` in
  `app/notifications/service.py`, called in-process by whichever rule has something to say.
  The OpenAPI document carries exactly two notification paths: `GET /notifications` and
  `POST /notifications/{id}/read`.
- `notify()` **flushes but does not commit.** A notification is almost always part of
  something larger — a cancellation that frees a car both deletes the booking and tells the
  next person in the queue — and those must land together or not at all. Committing inside
  would publish a notification about a transaction that could still roll back, telling
  someone their car is ready when it is not. Verified: a rolled-back transaction leaves no
  notification behind, and the flush still assigns an id so the caller can reference it.
- **Scope never widens for an admin.** Every other collection here shows an admin more:
  `GET /bookings` returns everyone's. This one does not, because a notification is addressed
  to a person rather than being business anyone may audit. An admin calling `GET
  /notifications` receives their own, which in practice is empty, and reaching for another
  user's by id answers `404` exactly as a registered user's attempt does.
- Marking read is **idempotent**: a second call answers `200` and leaves the original
  `read_at` alone, because what it records is when the user *first* saw this and a retried
  request must not rewrite that. There is no way to mark one unread — that would be a record
  of nothing.
- `read_at` is a nullable instant rather than a boolean. It answers strictly more ("has it
  been read" is `read_at is not None`, exposed as the derived `is_read`), and "when did they
  see this" is the question anyone debugging a missed notification actually asks. One fact,
  one column.
- `kind` is a short string, not a PostgreSQL enum: the set grows every time a feature starts
  emitting one, and an enum would make each of those a migration for a guarantee nothing
  needs. `NotificationKind` in the model lists the kinds that exist, and **only** those —
  naming the waitlist's kinds before the waitlist writes them would be a promise with no
  code behind it.
- The recipient foreign key is `ON DELETE CASCADE`, unlike the `RESTRICT` keys elsewhere: a
  notification means nothing without the person it addresses, so there is no history worth
  refusing a delete to protect. Verified by deleting a user and finding no orphan.
- **Nothing in the service emits a notification yet.** The waitlist (tickets 43 to 46) is the
  first producer. The fixture seeds two so the surface can be demonstrated at all, and they
  describe facts that are actually true of the fixture rather than invented events.

### The waitlist

- A **queue** is identified by a provider, a vehicle class and an **exact date range**. Two
  people wanting overlapping but different ranges are in different queues, which is what the
  requirement describes: capacity released for the 10th to the 12th is not capacity for the
  9th to the 15th, and pretending otherwise would offer people cars they cannot use.
- **Joining is refused with 409 when the class is not full** for those dates, and the refusal
  says how many cars are free and that the answer is to book it. A waitlist is for when you
  cannot have the thing; accepting an entry that could be converted into a booking
  immediately would be a worse answer than a sentence.
- Fullness is measured with `measure_room` — the one function booking, availability and the
  waitlist all share. "Full" means the same thing in all three by construction, not by
  coincidence. Ticket 40 is the reason this is stated: two copies of that arithmetic
  disagreed within one ticket.
- **One place per person per queue**; a second attempt is 409, guaranteed by a unique
  constraint on `(user_id, vehicle_class_id, start_date, end_date)`. The message says that
  joining twice would not move you up, because that is what someone trying it believes.
- **Position is derived from join order, never stored.** 1 is the front. A stored position
  would have to be rewritten for everyone behind anyone who leaves, and the first missed
  update would leave two people believing they were third. Leaving a queue therefore closes
  the gap immediately with no renumbering to go wrong.
- Order is `created_at` then `id`. The id tiebreak is not decoration: two entries written in
  the same microsecond would otherwise come back in whatever order PostgreSQL liked, and for
  a queue whose whole promise is strict FIFO that would be a silent lottery.
- The same date rules as booking creation: end on or after start, at most thirty days, and
  **no past-dated ranges** — queueing for days that have gone is refused at the shape level
  rather than accepted and quietly ignored.
- An entry whose range has since passed is **inert**: it stays visible as the holder's own
  record with `is_active: false`, and no release will be offered to it. A whole queue goes
  inert together, because the range is part of the queue's identity.
- **Deleting a booking offers the capacity it frees to the queue**, inside the same
  transaction and under the vehicle class row lock. Candidates are entries for that class
  that have not already been offered, whose range has not passed, and whose range now has
  room; the earliest joiner among them wins. Strict FIFO and strictly that — not the best
  fit, not whoever asks first.
- "Whose range the freed capacity satisfies" is answered by asking `measure_room` for that
  entry's range rather than by comparing date ranges. If the class is no longer full over
  the range someone wants, the release is usable by them; that is the same question booking
  asks, so the answer cannot disagree with it.
- An entry the release cannot satisfy is **skipped without losing its place**: not marked,
  not moved, not recorded as passed over, so the next release considers it in exactly the
  same position. This falls out of computing candidacy rather than storing it.
- `offered_at` is what takes an entry out of contention, which is what makes two
  cancellations in quick succession reach the first and then the *second* person rather than
  both reaching the first. A release nobody in the queue can use leaves every entry
  untouched and the capacity simply becomes available to anyone.
- **Nothing is booked automatically.** An offer is an opportunity; it creates no booking.
- The lock is taken **before** the delete and held across the offer, because deleting and
  then offering is two steps over one piece of state. Without it two simultaneous
  cancellations would both read the same queue, both find the same person at the front, and
  both offer them the capacity — one car promised twice and the second person never hearing
  anything. Verified by firing two cancellations at the same instant: the two releases reach
  two different people.
### Claims

- **An offer is a claim: a car held for one person until a deadline.** `offered_at` and
  `claim_expires_at` are written together and never apart, because an offer without a
  deadline would hold a car forever.
- **The window is configuration**: `CLAIM_WINDOW_MINUTES`, default **60**, must be greater
  than zero. The right value is a business judgement — long enough to notice an offer, short
  enough that a car is not held hostage — and a demo needs to watch one expire, so set it to
  `1` when demonstrating. A zero-minute window is refused at startup: it would expire in the
  instant it was created, so the offer could never be taken and the queue would drain itself
  silently.
- **A live claim occupies a car exactly as a booking does.** Both are counted in one per-day
  occupancy figure, so while a claim stands the class reads as full to everyone else even
  though a car is physically free, and a booking attempt is refused. The holder's own claim is
  excluded when they convert it — otherwise they would be refused by the very reservation made
  for them, which is the one thing an exclusive claim must never do.
- **The holder is notified**, through the notification records of ticket 42. This is the first
  thing in the service that writes one. `notify` flushes rather than commits, so the message
  lands with the cancellation that caused it or not at all.
- **Expiry is judged when the question is asked**, never by a background job — there is no
  scheduler in this project. A claim that lapsed overnight is simply not live the next time
  anyone reads or writes the queue, and the car it was holding is free again at that moment.
  Verified by backdating an expiry and finding the state `expired` and the capacity released
  with nothing having run in between.
- **Claim state is derived, never stored**: `waiting`, `claimed`, `expired`, `converted` or
  `declined`, computed from the timestamps on every read. A stored state and the timestamps
  behind it are two facts that can disagree, and the disagreement is always found later than
  it was caused. It is also what makes lazy expiry work at all.
- **Converting consumes the claim.** `POST /waitlist_entries/{id}/claim` creates the booking
  and sets `converted_at`; a second attempt answers 409. The class and dates come from the
  entry, not the body: the car is held for *those* days, and claiming it for others would be a
  new request rather than taking the offer.
- **Every other booking rule still applies to a conversion**: the provider must not have
  retired, the branches must be that provider's, an unenabled one-way direction is refused,
  and the owner's three-active cap holds. A claim offers a car; it does not exempt anyone from
  the rules about holding one.
- **Declining releases the car immediately** rather than making everyone behind wait out the
  expiry. `DELETE /waitlist_entries/{id}/claim`, 200 with `state: declined`. The entry stays
  visible as a record of what happened but is out of the queue.
- **Position counts only entries still in contention.** Converted, declined and expired
  entries are not counted ahead of anyone: once an entry can never be offered anything again,
  counting it would tell the person behind it they were further back than they are.
- Lock order note: a conversion holds the vehicle class row and then takes the owner row
  inside `ensure_room_for_another_booking`, which is the **reverse** of the order everywhere
  else. It is safe only because that route takes no further locks afterwards and no other path
  holds an owner row while reaching for a class row. If a future ticket adds one, this is the
  route to revisit.

### Passing a claim on

- **An expired or declined claim passes to the next entry whose range the capacity satisfies,
  and that person is notified.** Both cases go through one function, `settle_queue`, which is
  the same operation as offering capacity released by a cancellation — because an expired claim
  stops occupying a car the moment it expires, so capacity reappears on its own.
- **The expired holder loses their place.** They do not go to the back and they do not return
  to the front: their `offered_at` is set, so they can never be a candidate again. Like most of
  this feature, that is the absence of code rather than a rule.
- **Settling is lazy, and reads do it.** `GET /waitlist_entries` settles the queues the caller
  is in before reporting their places, as do joining, converting and declining, and deleting a
  booking. A GET with an effect is surprising enough to say out loud: the alternative is a
  background job, which this project does not have. Nothing is ever *wrong* in the meantime — a
  claim past its expiry is never honoured, because liveness is computed — the capacity it was
  holding has merely not been offered on yet. Verified with a week-old lapsed claim: nothing
  had been offered before anyone looked, and the first read settled it correctly.
- Settling offers **in a loop**, because more than one claim can have lapsed since anyone
  looked. Each offer re-reads occupancy, so the person offered a car immediately occupies it
  and the next pass sees the class full again: exactly one offer per free car, never two for
  one.
- **When nobody left can use what is free, the queue is untouched and the capacity is simply
  available to anyone.** Verified: the only waiter's claim lapsed, a read settled nothing, and
  an outsider booked the car.
- Settling runs under the vehicle class row lock, for the reason everything else here does.
  Verified by firing two reads of the same stale queue at the same instant: exactly one live
  claim existed afterwards, held by the person next in line.
- Only the queues the caller is actually in are settled on a read. Settling every queue in the
  system on every read would turn one person's list into a scan of the whole table.

### Admin scope on the waitlist

- **Admins do not join waitlists**, for the reason they do not hold bookings: a place in a
  queue is a claim on inventory, and they manage rather than rent. Another user's entry
  answers 404, for an admin too — nothing in the requirement asks an admin to administer a
  queue, and narrow scope means the ordering rules have one code path rather than two.

### Providers

- `GET /providers` excludes retired providers and carries `average_rating` and
  `review_count` for each. An admin may pass `include_retired=true` to see retired
  providers as well; the same parameter from a registered user is ignored, so retired
  providers never reach them.
- `POST /providers/{id}/reinstate` returns a retired provider to the catalogue. Retirement
  is reversible, per ADR 0004.
- `average_rating` is computed on read by aggregation, never stored. A provider with no
  reviews returns `null`, not `0`. Rounded to one decimal place in responses, stored at
  full precision.
- `GET /providers/{id}` returns retired providers too, so users can see who they booked.
- `DELETE /providers/{id}` retires; it never removes the row.
- `GET /providers/{id}/availability?start_date=&end_date=` returns the number of cars free
  for the whole requested period for each of that provider's vehicle classes. **Free means
  both unbooked and on the road:** since ticket 40 a car with a blackout window overlapping
  any day of the range is not counted at all, because a car in the workshop for part of the
  range cannot be rented for the range. A class with no free car reports `free_count: 0` and
  is never omitted, so a caller can distinguish "full" from "does not exist" — this is why
  the blackout test sits in the join condition rather than a `WHERE` clause, which would
  make a wholly blacked-out class disappear instead of reporting zero. Retired providers
  answer 404, matching the catalogue list. The same date shape rules as booking creation
  apply (end on or after start, at most 30 days); violations answer 422. The no-past-start
  rule does not apply. Any authenticated caller may use this route.
- **Availability and booking agree, in both directions and for both reasons.** Since
  ticket 41 they perform the same arithmetic — vehicles in the class, minus those off the
  road for any day of the range, against the busiest day's bookings — so `free_count: 0`
  always means booking is refused and one or more always means it succeeds, whether the
  shortfall is demand or maintenance:

  ```
  SUV over its own blackout                 free=0  booking=409
  Economy, 2 of 3 blacked out + 1 booked    free=0  booking=409
  Economy on a clear range                  free=3  booking=201
  ```

### Vehicle classes

- A class belongs to exactly one provider and never moves. The provider is set at
  creation from the path, and the update shape carries no field for it, so there is no
  request that could express a move.
- Names are unique within a provider and compared without regard to case: "SUV" and
  "suv" are the same kind of car to a reader. Two different providers may each offer an
  "SUV". A duplicate is refused with 409. A unique index on `(provider_id, lower(name))`
  is what guarantees it; the handler's own lookup exists only to produce a readable
  message in the ordinary case.
- Removal is a real delete, not retirement — a class is catalogue housekeeping, not a
  party to a booking. But a class that anything else still points at is refused with 409
  rather than cascading, so history is never destroyed by tidying the catalogue. Every
  table that comes to reference a vehicle class does so `ON DELETE RESTRICT`; since
  ticket 24 that includes vehicles, so removing a class that still has cars answers 409.
- Classes under a retired provider remain listable and fetchable, matching how retired
  providers themselves behave. Adding a class to a retired provider is also allowed:
  retirement stops new bookings, and this is not one.

### Vehicles

- A vehicle sits in exactly one vehicle class. It may be reclassified within the same
  provider's catalogue — a car really does move from Economy to Compact — but moving it
  to another provider's class is refused with 409: that is a sale, not a
  reclassification.
- Plates are unique across the whole system, not per provider, and compared without
  regard to case. A plate identifies a car on the road; the same one under two providers
  would mean one of them is wrong. A duplicate is refused with 409, guaranteed by a
  unique index on `lower(plate)`.
- The fleet is admin-only to read. A plate is fleet administration and of no use to a
  renter, who books a kind of car. What a renter needs is the count, reported as
  `vehicle_count` on the vehicle class itself and readable by any authenticated user.
- `vehicle_count` is computed on read by aggregation, never stored, for the same reason
  a provider's `average_rating` is: a stored count drifts the moment a car is added or
  removed outside the one code path that maintains it. It is the capacity that becomes
  enforceable in ticket 26; nothing yet refuses a booking because of it.
- Removing a vehicle is a real delete, but a car that anything else still points at — a
  maintenance blackout window, since ticket 39 — is refused with 409 rather than
  cascading. Every table that references a vehicle does so `ON DELETE RESTRICT`.
- A vehicle's own foreign key to its class is `ON DELETE RESTRICT`, which is what makes
  the vehicle class in-use refusal above real: removing a class that still has cars in it
  answers 409.

### Maintenance blackout windows

- A **blackout window** is a period during which one vehicle is off the road for
  servicing. Scheduled per vehicle, never per vehicle class: a workshop takes one car in,
  not a category. This is the feature individual vehicles were modelled for.
- Dates are inclusive at both ends, like every other period here: a window whose start
  and end dates are equal is one day.
- **A window may be scheduled wholly in the past.** A rental cannot, because nobody can
  rent a car for days that have gone; a service can certainly have happened last week,
  and recording it is how the schedule stays honest. An admin correcting last month's
  entry is ordinary work.
- **There is no maximum length.** A rental period caps at thirty days so one booking
  cannot hold a slot indefinitely. A car can be off the road for months after a crash,
  and a cap would only force an admin to record it in instalments.
- **Two windows on the same vehicle may not overlap: the second is refused with 409, not
  merged.** Both were available and the choice is recorded here because it is visible
  behaviour. Merging would answer a different request from the one that was sent — an
  admin asking for the 10th to the 12th would get 201 and find a window from the 1st to
  the 20th — and the two service visits that produced them would become one record
  matching neither. The refusal names the window in the way and the two remedies the
  surface already supports: widen it, or cancel it.
- **The overlap boundary.** Inclusive, so adjacency is not overlap: a window ending on
  the 9th does not clash with one starting on the 10th, and a one-day window clashes only
  with periods containing that very day. Guaranteed by an exclusion constraint,
  `EXCLUDE USING gist (vehicle_id WITH =, daterange(start_date, end_date, '[]') WITH &&)`,
  which needs the `btree_gist` extension — created by the migration, trusted since
  PostgreSQL 13 so no superuser is required.
- Scheduling takes two row locks, the vehicle class and then the vehicle. The vehicle guards
  the overlap check against another window being inserted concurrently; **the class is locked
  only so that this path contends with booking's capacity count**, which since ticket 41
  includes cars off the road. Without it, a booking could read "one car free, none in the
  workshop" at the moment this inserts the window that makes that false, and be accepted on a
  reading already stale. **Lock order** is owner, then vehicle class, then vehicle — every
  path that takes more than one takes them this way round.
- A window carries no free-text reason. Nothing asks for one, and an empty field invites
  being filled with the rule it was meant to explain.
- A window's foreign key to its vehicle is `ON DELETE RESTRICT`: a car with a service
  history cannot be removed until its windows are cancelled, which answers 409.
- **A window both reduces availability and refuses a booking.** Ticket 40 took blacked-out
  cars out of `GET /providers/{id}/availability`; ticket 41 made booking and re-dating refuse
  for the same reason, with the same arithmetic, so the two can no longer disagree.
- **Scheduling a window over a booking that already exists is allowed, and the booking
  stands.** The alternatives were refusing the window or flagging the booking, and both were
  rejected. Refusing would mean the database cannot record a car that has broken down, which
  is the one thing maintenance scheduling exists for — reality does not ask permission.
  Flagging would add a field to a booking that nothing reads and no rule acts on. So the
  window is written, every existing booking is untouched, and the class is simply
  over-committed for those days: availability reports the lower number immediately, and new
  bookings are refused. Nobody's rental quietly disappears, which is the part that matters.
  An admin who needs the car back has to talk to the renter and delete the booking, which is
  what would happen in the world anyway.
- Nothing stops a window being scheduled over a booking **by accident**, and that is a real
  cost of this choice. It is accepted knowingly: the alternative silently loses the ability
  to record facts.

### What a nested resource carries

A resource that appears **inside** another — the provider and vehicle class in a booking, the
branches — carries **only stored columns**. Never a field computed by aggregation.

This is a rule rather than a style, and it was paid for. `average_rating` and `review_count`
are not columns; they come from an aggregate the provider routes run. `BookingRead` nested the
full `ProviderRead`, so validating it from a `Provider` object found no such attributes and
fell back to the field defaults — and every booking reported a confident `null` and `0` for a
provider with a four-star average. Same provider, same request second, two different answers.

Fixed in ticket 50 by **removing the fields from the nested shape** rather than filling them
in wherever a booking is built. Two reasons:

- A field that is sometimes a lie is worse than an absent one. Populating the aggregate in
  every route that returns a booking leaves the same trap set for the next person who nests
  something, and the booking *list* route would run it per row.
- A booking says who it is with and how to reach them. What other people think of them is
  catalogue information — for choosing a provider, not for the record of a rental already
  made — and `GET /providers` is where you choose.

So there are two shapes per resource where the difference matters: `ProviderSummary` and
`ProviderRead`, `VehicleClassSummary` and `VehicleClassRead`. The summary is what nests. The
full shape is only ever built by the routes that run the aggregate.

**If you nest a resource, nest its summary.** If it has no summary and carries a computed
field, write one.

### Authorization

- Users and admins share the same routes. Scope widens by role: `GET /bookings` returns
  your own bookings, or all of them for an admin. The same widening applies to a booking
  addressed by identifier — fetching, re-dating and deleting all resolve through one
  lookup, so a registered user reaches only their own and an admin reaches any.
- Every request schema sets `extra="forbid"` and every id field it accepts is bounded
  `1..2147483647`. These are not stylistic: without the first, a field the caller believes
  they set is silently thrown away, and without the second an over-large id reaches
  PostgreSQL and raises `NumericValueOutOfRange`, which surfaces as a 500. Response shapes
  need neither, since nothing untrusted is validated through them.
- Acting on a booking you do not own returns `404`, not `403`, so that booking ids
  cannot be enumerated. The answer is identical whatever the verb and whatever else is
  wrong with the request, so ordering cannot be used to probe either.
- Admin-only provider routes answer `403` rather than `404`, whether or not the provider
  exists: the role is resolved before the lookup, and provider existence is readable by
  any authenticated user anyway.

### Branches

- A branch is a physical pickup location belonging to exactly one provider. A provider
  must always have at least one branch. Removing the last branch is refused with 409.
- A branch has a name, address, and telephone. The provider retains its own address and
  telephone columns — those are the general business contact details in catalogue and
  booking responses. A branch address is the specific pickup location.
- Created under the provider (`POST /providers/{id}/branches`), listed there
  (`GET /providers/{id}/branches`, ordered by name then id), and addressed directly:
  `GET /branches/{id}`, `PATCH /branches/{id}`, `DELETE /branches/{id}`.
- Reads are open to any authenticated caller; create, edit and remove are admin-only and
  answer 403.
- Removing a branch named by a booking answers 409 rather than cascading.
- `DELETE /branches/{id}` answers 204 with no body.
- Migration `cb0b6c819227` created the table and seeded one "Main Branch" per existing
  provider using the provider's address and telephone, so no provider was left without one.
- Removing a branch cascades to its distances (ON DELETE CASCADE on `branch_distances`).

### Delivery radius

- A branch may carry a delivery radius in kilometres, recording how far that branch will
  bring a car to a customer. A branch with no radius set does not offer delivery at all;
  this is distinct from a radius of zero.
- Set with `PUT /branches/{id}/delivery-radius` (body: `{"kilometres": N}`, N ≥ 0).
  Cleared with `DELETE /branches/{id}/delivery-radius`, which answers 204 with no body.
  Both routes are admin-only and answer 403 for a registered user.
- A negative radius is refused with 422.
- Any authenticated caller can see the radius via the existing `GET /branches/{id}` and
  `GET /providers/{id}/branches` responses; the field `delivery_radius_km` is null when
  no radius is set.
- Clearing the radius leaves existing bookings that used delivery untouched.
- Migration `abc1def23456` added the nullable `delivery_radius_km` column; existing rows
  default to null (no delivery).

### Delivery on a booking

- A booking may carry a `delivery_address` (text) and `delivery_distance_km` (integer,
  caller-supplied). Both must be provided together or both omitted; providing one without
  the other is refused with 422.
- Omitting both is the ordinary case: the customer collects from the branch.
- A blank delivery address is refused with 422. A negative `delivery_distance_km` is refused
  with 422 (`ge=0` on the schema).
- When delivery is requested, the pickup branch must have a delivery radius set; a branch
  with no radius is refused with 409. A distance greater than the branch radius is refused
  with 409, naming the radius so the caller knows by how much. A distance exactly equal to
  the radius is accepted (inclusive boundary).
- A booking may also carry a `collection_address`. Null means the car is collected from the
  same address it was delivered to. `collection_address` without `delivery_address` is
  refused with 422.
- All three fields are returned on every booking response (`null` when not set).
- Migration `bcd2ef34567a` added the three nullable columns to `bookings`. It is a merge
  migration combining the delivery-radius chain (ticket 36) and the teammate's waitlist
  chain (tickets 39–45), both of which branched from `1228c9d212a5`.

### Branch distances

- An admin records the distance in kilometres between two of the same provider's branches.
  Distance is symmetric: one row covers both directions. Application code stores the pair
  in canonical form (smaller id first) and normalises every read and write the same way.
- Recorded with `PUT /providers/{id}/branch_distances` (body: `from_branch_id`,
  `to_branch_id`, `distance_km`). Submitting the same pair again updates rather than
  duplicating. Read with `GET /providers/{id}/branch_distances/{a}/{b}`; removed with
  `DELETE /providers/{id}/branch_distances/{a}/{b}`.
- Reads are open to any authenticated caller; create, edit and remove are admin-only (403).
- A branch that does not exist answers 422; one that belongs to a different provider
  answers 409. A branch paired with itself is refused with 422. A negative or zero distance
  is refused with 422.
- A missing distance answers 404 — it is never assumed to be zero, since a zero relocation
  fee and an unknown one are different things.
- `DELETE /providers/{id}/branch_distances/{a}/{b}` answers 204 with no body.

### One-way routes

- An admin enables one-way rental from one branch to another for the same provider.
  Enablement is **directional**: enabling A→B does not enable B→A; each direction is an
  independent row.
- Enabling a pair that has no recorded distance is refused with 409, since the relocation
  fee could not then be computed.
- Enabled with `PUT /providers/{id}/one_way_routes` (body: `from_branch_id`,
  `to_branch_id`). Idempotent: submitting an already-enabled pair returns the existing
  row unchanged. Disabled with
  `DELETE /providers/{id}/one_way_routes/{from_id}/{to_id}`, which answers 404 if the
  route was not enabled. Listed with `GET /providers/{id}/one_way_routes`, ordered by
  from_branch_id then to_branch_id.
- Reads are open to any authenticated caller; enable and disable are admin-only (403).
- A branch that does not exist answers 422; one that belongs to a different provider
  answers 409. A branch paired with itself is refused with 422.
- Disabling a route leaves any existing bookings that used it untouched.
- Removing a branch cascades to its one-way routes (ON DELETE CASCADE on
  `one_way_routes`).

### Money

- All monetary amounts are stored as exact decimals (`NUMERIC(12,2)`), never as floating
  point. Two bookings with the same rate must produce the same total on every machine.
- The service operates in a single currency, named in configuration as `CURRENCY`
  (default `THB`). No currency conversion occurs.
- Rounding is half-up to two decimal places, applied in one place (`app/core/money.py`).
- Amounts appear in responses as `{"amount": "<string>", "currency": "<code>"}`. The
  amount is a string to preserve the exact decimal value across the JSON boundary; a
  JSON number would invite float conversion.
- `null` means the item has not been priced yet ("unpriced"). Zero is a valid rate and
  means free. These are never conflated.

### Vehicle class surface

- Created under the provider (`POST /providers/{id}/vehicle_classes`), since a class
  cannot exist without one, and listed there (`GET /providers/{id}/vehicle_classes`,
  ordered by name then id). Thereafter addressed directly:
  `GET /vehicle_classes/{id}`, `PATCH /vehicle_classes/{id}`,
  `DELETE /vehicle_classes/{id}`.
- Editing is a `PATCH` because name and description are genuinely independent, as with
  providers.
- `DELETE /vehicle_classes/{id}` answers 204 with no body. It really removes the row.
- Reads are open to any authenticated caller; create, edit and remove are admin-only and
  answer 403, consistent with the provider routes they mirror.
- A vehicle class carries an optional daily rate (`daily_rate`), set at creation or via
  `PATCH`. A negative rate is refused with 422. Zero is valid (free). Null means
  unpriced. Sending `daily_rate: null` in a `PATCH` removes the rate. Omitting
  `daily_rate` from a `PATCH` leaves it unchanged. The rate appears in every vehicle
  class response, including the summary nested in booking responses.

### Vehicle surface

- Created and listed under the class (`POST` / `GET /vehicle_classes/{id}/vehicles`,
  ordered by plate then id), then addressed directly: `GET /vehicles/{id}`,
  `PATCH /vehicles/{id}`, `DELETE /vehicles/{id}`.
- Every one of those is admin-only and answers 403 to a registered user, reads included —
  the only route in the service where a read is privileged, because the plate is the
  privileged part.
- `DELETE /vehicles/{id}` answers 204 with no body.
- A `PATCH` naming a vehicle class that does not exist answers 422, not 404: the missing
  thing is a value in the body, not the resource the path addresses, and the vehicle
  itself was found.

### Blackout window surface

- Created and listed under the vehicle (`POST` / `GET
  /vehicles/{id}/blackout_windows`, ordered by start date then id), then addressed
  directly: `GET /blackout_windows/{id}`, `PUT /blackout_windows/{id}`,
  `DELETE /blackout_windows/{id}`.
- **Reading is open to any authenticated user; writing is admin-only (403).** This is the
  one place a vehicle-shaped route is readable by a registered user, and deliberately so:
  that a car is off the road is not confidential, and a renter who has been refused has a
  right to see why. The plate is still not exposed — a window carries `vehicle_id`, and
  the refusal message that names a plate goes only to the admin who caused it.
- `PUT` replaces the period and carries no `vehicle_id`; sending one answers 422. A window
  records what happened to a particular car, so pointing it at another car would not be an
  edit but a fabrication. Cancel it and schedule one on the right car.
- `DELETE /blackout_windows/{id}` answers 204 with no body. Nothing references a window,
  so it never conflicts; the car is back on the road immediately and there is no cancelled
  state to inspect.

### Notification surface

- `GET /notifications` — the caller's own, newest first, ordered by `created_at` then `id`,
  both descending. The id tiebreak is not decoration: two notifications written in one
  transaction can carry timestamps a microsecond apart, and without it the order would vary
  between runs. A user with none receives `[]`, never an error.
- `POST /notifications/{id}/read` — marks it read and returns it. `200`, idempotent.
- Another user's notification answers `404`, including for an admin. An over-large id answers
  `422` from the path bound.
- There is no `GET /notifications/{id}` and no unread count. Neither is asked for, and a
  client that has the list needs neither.
- Both routes require authentication; neither has an admin variant.

### Waitlist surface

- `POST /providers/{id}/waitlist_entries` — join, with `vehicle_class_id`, `start_date`,
  `end_date`. 201 with your `position` and `is_active`.
- `GET /waitlist_entries` — your own places, each with `position`, ordered by the range
  wanted then by when you joined. None gives `[]`.
- `DELETE /waitlist_entries/{id}` — leave. 204, no body.
- An entry carries `offered_at`, `claim_expires_at`, `converted_at`, `converted_booking_id`,
  `declined_at`, and a derived `state`.
- `POST /waitlist_entries/{id}/claim` — take the claim as a booking. 201 with the **booking**,
  not the entry. Body carries only `pickup_branch_id` and optionally `dropoff_branch_id`.
- `DELETE /waitlist_entries/{id}/claim` — decline it. 200 with the entry.
- Both answer 409 when there is no live claim, naming which of the four states applies, and
  404 for another user's entry — for an admin too.
- There is no route that lists a whole queue, and no route that shows another person's place.
  Who else is waiting is not the caller's business; their own position is all they need, and
  publishing the queue would let anyone measure a provider's demand.

### Quotation surface

- `POST /providers/{id}/quotations` — any authenticated caller; unauthenticated is 401.
- Accepts the same fields as booking creation: `vehicle_class_id`, `pickup_branch_id`,
  `dropoff_branch_id` (optional), `start_date`, `end_date`. The same validation applies:
  date ordering, 30-day maximum, no past start date, class and branches must belong to the
  provider, one-way route must be enabled when a different drop-off branch is named.
- Returns `{"lines": [...], "total": {...}}`. Each line has `description` and `amount`
  (a `Money` object). The rental line is `daily_rate × rental_period_days`, where days
  are counted inclusively. The total is the sum of all lines, rounded once using
  `round_amount()` from `app/core/money.py`.
- For a one-way rental (different drop-off branch), a second **relocation line** is added:
  `distance_km × relocation_rate_per_km`. The rate is configurable via `RELOCATION_RATE_PER_KM`
  (default **THB 50.00/km**). A same-branch rental carries no relocation line.
- When `delivery_address` and `delivery_distance_km` are both provided, a **delivery and
  collection line** is added. The charge is determined by the tier the distance falls in.
  Tiers are configurable via `DELIVERY_TIERS` (JSON array, each entry `{"max_km": N,
  "charge": "X.XX"}`). Default tiers (THB):

  | Distance (km) | Charge |
  |---|---|
  | 0 – 10 | 200.00 |
  | 11 – 20 | 400.00 |
  | 21 – 50 | 800.00 |

  The upper bound of each tier is **inclusive**: a distance exactly equal to `max_km`
  falls in that tier. A distance beyond every tier is refused with 409 (not silently
  charged at the top tier). The charge covers both delivery and collection as one line.
  Omitting delivery fields means no delivery line.
- A vehicle class with no `daily_rate` set answers 409 ("unpriced").
- A quotation reserves nothing; calling it twice with the same inputs returns the same
  result.

### Booking surface

- Created under the provider (`POST /providers/{id}/bookings`), since a booking cannot
  exist without one. Thereafter addressed directly: `GET /bookings`,
  `GET /bookings/{id}`, `PUT /bookings/{id}`, `DELETE /bookings/{id}`.
- Re-dating is a `PUT` carrying both dates rather than a `PATCH` of either. A rental
  period is one value with two halves, so replacing it wholesale keeps the date rules on
  the request schema, where they answer 422, instead of validating a merge of stored and
  supplied values in the handler. Provider editing is a `PATCH` because its fields are
  genuinely independent.
- `DELETE /bookings/{id}` answers 204 with no body. Provider deletion answers 200 with the
  record because it retires rather than removes; this one really deletes.
- A booking response nests the provider and the vehicle class. The class is nested as a
  **summary** — id, provider, name, description — and deliberately without
  `vehicle_count`, because that number comes from an aggregate query rather than from the
  model and would otherwise be reported as a confident zero. The nested provider does not
  yet observe the same discipline: `average_rating` and `review_count` inside a booking
  are always `null` and `0`. That is a known defect, recorded as ticket 50.

## Auth

Stateless JWT, 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`), no refresh token. Logout is
client-side; the endpoint exists and invalidates nothing. Passwords are hashed with
bcrypt, minimum 8 characters and at most 72 bytes, never returned. Registration returns a
token directly.

The `bcrypt` library is used directly rather than through passlib, which this document
originally named: passlib's last release was 2020 and its bcrypt backend fails outright
against bcrypt 5.x, which it probes for a `__about__` attribute that no longer exists.
The alternative was pinning an old bcrypt to keep passlib working, and the password
hashing library is the last dependency worth freezing. The 72-byte ceiling is bcrypt's
own limit, not a policy choice; over-long passwords are rejected as unprocessable rather
than silently truncated.

`JWT_SECRET_KEY` must be at least 32 bytes, per RFC 7518 for HS256, and startup fails
otherwise: a short signing key is brute-forceable, and a forged token would defeat every
authorisation rule in the service. Logging in with an unknown email spends the same time
as a wrong password, so registered addresses cannot be found by timing the refusal.

Validation errors never echo a rejected password. Pydantic reports the offending value
alongside each error by default, which would put a plaintext password in a response body
and from there into logs and proxies; a handler redacts it and changes nothing else about
the error shape.

## Status codes

| Situation | Code |
|---|---|
| Fourth active booking | 409 |
| Booking a retired provider | 409 |
| Reviewing a booking that has not ended | 409 |
| Reviewing a booking twice | 409 |
| Registering an email that is already in use | 409 |
| Logging in with a wrong password or an unknown email | 401 (same response for both) |
| A missing, malformed, expired, or forged access token | 401 |
| Malformed input (date order, rating range, max length, password length) | 422 |
| Sending an unexpected field, such as `role`, on registration | 422 |
| Acting on another user's booking | 404 |
| An admin trying to create a booking of their own | 403 |
| Deleting a booking | 204, no body |
| Sending `provider_id` when re-dating a booking | 422 — refused, never silently ignored |
| A registered user on an admin-only provider route | 403, whether or not the provider exists |
| Re-dating a reviewed booking so it would not yet have ended | 409, reported ahead of the cap |
| A path **or body** id larger than an integer primary key can hold | 422 |
| Booking with no vehicle class, or one outside integer range | 422 |
| Booking a vehicle class that does not exist | 422 (a body value, not the path) |
| Booking a vehicle class belonging to a different provider | 409 |
| Booking with a pickup branch that does not exist | 422 (a body value, not the path) |
| Booking with a pickup branch belonging to a different provider | 409 |
| Sending `pickup_branch_id` when re-dating a booking | 422 — refused, never silently ignored |
| Recording a distance between branches of different providers | 409 |
| Recording a distance from a branch to itself | 422 |
| Recording a negative or zero distance | 422 |
| A branch in a distance request that does not exist | 422 (body value) |
| Fetching a distance that has not been recorded | 404 |
| A registered user on a branch distance write route | 403 |
| Removing a branch distance | 204, no body |
| Removing the last branch under a provider | 409 |
| Removing a branch named by a booking | 409 |
| A registered user on any branch write route | 403 |
| Removing a branch | 204, no body |
| Availability search on a retired provider | 404 |
| Availability search with end before start, or period over 30 days | 422 |
| Availability for a class whose every car is blacked out over the range | 200, `free_count: 0` — never omitted |
| A blackout window ending the day before the range starts | does not reduce `free_count` |
| A blackout window starting on the final day of the range | reduces `free_count` |
| Booking a class whose vehicles are all taken on any day of the period | 409 "is fully booked" |
| Booking a class that has no vehicles at all | 409 "it has no vehicles" |
| Booking a class whose every vehicle is off the road for maintenance for part of the period | 409 "off the road for maintenance … try different dates" |
| Booking a class short of cars through maintenance *and* bookings together | 409 naming both counts |
| Re-dating a booking into a period where its class is full, for any of those reasons | 409, for owner and admin alike |
| Scheduling a blackout window over a booking that already exists | 201 — allowed; the booking stands |
| Sending `vehicle_class_id` when re-dating a booking | 422 — refused, never silently ignored |
| A duplicate vehicle class name under one provider, in any case | 409 |
| Removing a vehicle class that something still references | 409 |
| Sending `provider_id` when editing a vehicle class | 422 — refused, never silently ignored |
| A registered user on an admin-only vehicle class route | 403, whether or not the class exists |
| Removing a vehicle class | 204, no body |
| A duplicate plate anywhere in the system, in any case | 409 |
| Moving a vehicle to another provider's class | 409 |
| Naming a non-existent vehicle class when editing a vehicle | 422 (a body value, not the path) |
| Removing a vehicle that something still references | 409 |
| A registered user on any vehicle route, read or write | 403 |
| Removing a vehicle | 204, no body |
| Scheduling a blackout window overlapping another on the same vehicle | 409 — refused, never merged |
| A blackout window adjacent to another (ending the day before it starts) | 201 — adjacency is not overlap |
| A blackout window with `end_date` before `start_date` | 422 |
| A blackout window wholly in the past | 201 — a service that happened is a fact |
| Sending `vehicle_id` when re-dating a blackout window | 422 — refused, never silently ignored |
| Scheduling a blackout window on a vehicle that does not exist | 404 |
| A registered user reading blackout windows | 200 — the one vehicle-shaped read a user may do |
| A registered user on a blackout window write route | 403, whether or not the window exists |
| Removing a vehicle that has a blackout window | 409 |
| Cancelling a blackout window | 204, no body |
| Listing notifications with none | 200, `[]` |
| Marking a notification read | 200, the notification |
| Marking an already-read notification read again | 200, `read_at` unchanged |
| Another user's notification, or an admin reaching for one | 404 |
| A provider nested in a booking | stored columns only; no `average_rating`, no `review_count` |
| Any attempt to create a notification through the API | 404 or 405 — no such route exists |
| Joining a waitlist for a class that is not full | 409, naming how many cars are free |
| Joining a queue you are already in | 409 |
| Joining with a past-dated, reversed or over-long range | 422 |
| Joining for a class belonging to another provider | 409 |
| Joining a retired provider's queue | 409 |
| An admin joining a waitlist | 403 |
| Another user's waitlist entry, or an admin reaching for one | 404 |
| Leaving a waitlist | 204, no body |
| Deleting a booking when someone is waiting who can use it | 204; the earliest such entry gains `offered_at` |
| Deleting a booking when nobody waiting can use it | 204; every entry untouched |
| Booking a class whose only free car is held by someone else's live claim | 409 "fully booked" |
| Converting your own live claim | 201 with the booking, even though the class reads as full |
| Converting a claim twice | 409 "a claim can only be taken once" |
| Converting an expired claim | 409, judged at that moment with nothing having run |
| Converting when nothing was offered | 409 "you are still in the queue" |
| Declining a live claim | 200, `state: declined`, capacity free immediately |
| Declining twice | 409 |
| Another user's claim, or an admin reaching for one | 404 |
| Reading your waitlist entries when a claim ahead of you has lapsed | 200, and you now hold the claim |
| A lapsed claim when nobody else can use the capacity | the car becomes bookable by anyone |

## Seeding and testing

`python -m app.seed` wipes and recreates demo data, and refuses to run when
`ENV=production`. Re-running is safe and always produces the same state.

What it creates, and why each piece has to be there:

| | | Why |
|---|---|---|
| 1 admin, 5 users | `admin`, `demo`, `fresh`, `alpha`, `beta`, `gamma` | `demo` holds bookings to act on; `fresh` holds none; `alpha` fills the SUV class; `beta` and `gamma` are in the waitlist queue |
| 4 providers | one of them retired | the retired one proves bookings survive retirement |
| 5 branches | two under the first provider; Siam has `delivery_radius_km=20`, Don Mueang has none | a booking must name a pickup branch; one-way needs two; one branch with delivery and one without so both outcomes are demonstrable |
| 1 inter-branch distance | Siam ↔ Don Mueang, 27.5 km | one-way enablement is refused without a recorded distance |
| 1 one-way route | Siam → airport, **one direction only** | the directional refusal is the easiest one-way rule to get wrong, and enabling both ways would hide it |
| 5 vehicle classes | one per provider, two for the first | a booking must name a class |
| daily rates on 4 of the 5 | "Classic" left unpriced | so a quotation can be shown refusing to price a class rather than quoting zero |
| 10 vehicles | Economy 3, SUV 1, Van 2, Classic 1 | a class with no cars refuses every booking; the uneven counts let a demo fill the one-car class in a single request |
| 3 bookings | `demo` ended (one-way) + `demo` upcoming (round-trip) + `alpha` SUV (fills the class) | one of each shape; the ended one is reviewable; the SUV booking makes the waitlist joinable immediately without first filling it by hand |
| 0 reviews | | the demo performs the first one |
| 2 notifications for `demo` | one read, one unread | nothing in the service emits one yet; one of each state so "newest first" and "has it been read" are both visible |
| 1 blackout window | one Economy vehicle, today+2 to today+6 | demonstrates `free_count: 2` (not 3) during that range, and maintenance-overlap refusal |
| 2 waitlist entries | `beta` (position 1) + `gamma` (position 2) for SUV, same range as alpha's booking | FIFO order is visible without manually queuing mid-demo |

The ended booking is inserted through the ORM, bypassing the no-past-dates rule, which
exists to protect users rather than to constrain fixtures.

**The fixture is part of the contract**, and it has now broken three times, in two
different ways:

- **A newly required column.** The fixture writes rows through the ORM, not the API, so a
  column that becomes `NOT NULL` crashes it on a `NotNullViolation`. Ticket 25's vehicle
  class and ticket 29's pickup branch both did this, and both were found by someone trying
  to demo rather than by the ticket that caused them.
- **A new table referencing an existing one with `ON DELETE RESTRICT`.** The wipe runs
  children before parents, so a table missing from `_WIPE_ORDER` blocks the delete of the
  one it points at. Ticket 39's blackout windows did this — caught before merging, because
  running the seed is now part of closing a ticket.

So: **run `uv run python -m app.seed` before closing any ticket that adds a table or
touches a model**, and if the new table references another with `RESTRICT`, add it to
`_WIPE_ORDER` above the table it points at.
Ticket 47 rebuilds the fixture.

### Verification

There is **no automated test suite** — no unit tests, nothing in CI, nothing mocked. That
decision stands. Two things exist instead, and they are not the same thing:

| | What it is | What it is for |
|---|---|---|
| `python -m app.smoke` | One command that calls the real API over HTTP against a running app and a seeded database, asserting **status codes only** | Catching a break. Ours, not a reader's |
| The Postman collection (ticket 22) | Requests organised by area, asserting on payloads, with a README walkthrough | Demonstrating behaviour. What a reader is shown |

`app/smoke.py` is deliberately **not** the suite that was decided against: it is a single
script with no framework, no fixtures and no mocks, which a developer runs by hand. It
asserts status codes and nothing else, because response shapes churn — a booking's request
body has gained three fields since the collection was first specified — and a check that
fails whenever someone adds a column is a check people learn to ignore. `201` stays `201`
when a payload grows a field, so a failure there is always real.

It discovers providers, classes, branches and one-way routes through the API rather than
assuming seeded ids, computes dates through `today()` so it cannot disagree with the server
about the date, registers its own throwaway users, and deletes every booking and review it
creates — so it can be run repeatedly without re-seeding. It exits `0` on success, `1` on a
failed check, and `2` when its preconditions are not met, which is the case that would
otherwise read as a wall of false failures.

It exists because three defects on this project were found by accident rather than by
checking: `app/seed.py` broke twice when a booking column became required (tickets 25 and
29), and `OneWayRouteEnable` silently discarded a field and answered 200. All three are
first-failure material for a run like this.

Dates in the Postman collection are computed in pre-request scripts relative to now, never
hardcoded, so that requests do not go stale.
