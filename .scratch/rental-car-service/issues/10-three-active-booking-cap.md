# 10 — Three-active-booking cap

**What to build:** A registered user may hold at most three active bookings — bookings
whose rental period has not yet ended. A fourth is refused with a message that explains
the limit rather than leaving the user guessing. Bookings whose periods have ended stop
counting, so past rentals do not permanently consume the allowance.

**Blocked by:** 08

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] A registered user can hold three active bookings
- [x] A fourth active booking is refused as a conflict, not as malformed input
- [x] The refusal message states that the user already holds three active bookings
- [x] A booking whose rental period has ended does not count toward the limit
- [x] The count is measured against the booking's owner, not the caller
- [x] Two bookings with overlapping rental periods are permitted, since no vehicle
      inventory is modelled and the cap already bounds abuse
- [x] The limit is counted using the business-timezone helper, not the system clock

## Notes

- Verified live: Alice holds three bookings and is refused a fourth with 409 and a message
  naming the limit. Bob booking at the same time is unaffected, so the count is per owner.
- All three of Alice's bookings deliberately **overlap**. Overlap is permitted: with no
  vehicle inventory two overlapping bookings contradict nothing, and the cap already bounds
  abuse.
- 409, not 422. The request is well formed; it is the stored state that refuses it. That
  distinction is the one in `docs/SPEC.md`'s status table.
- The ended-booking criterion cannot be reached through the API, because past-dated
  creation is forbidden, so it was checked by writing directly through the ORM — the same
  manoeuvre ticket 14's seed will use. With three active plus one ended, a fourth is still
  refused; backdating one active booking so it ends yesterday frees exactly one slot, the
  next booking succeeds, and the one after that is refused again.
- Boundary checked explicitly: a booking ending **today** still counts as active, one
  ending **yesterday** does not.
- The timezone rule was proved by changing `BUSINESS_TIMEZONE`: Pacific/Kiritimati and
  Pacific/Midway report different days, so the line between active and ended moves with the
  setting rather than with the machine clock. A direct demonstration against UTC was not
  possible at the hour this ran, because the business day and the UTC day happened to agree.
- Both rule functions take a `user_id` and neither reads the authenticated caller. Ticket
  20 depends on that: an admin editing someone else's booking must be measured against the
  booking's owner.

### Removed before merging

A first draft gave the count an `excluding_booking_id` parameter so ticket 12 could exclude
the booking being re-dated. Nothing in this ticket used it. That is speculative generality
— a hook for a need that does not exist yet — and it was taken out. Ticket 12 should add it
when it is real.

### Corrected after audit

The cap shipped as a plain count-then-insert with no lock, at READ COMMITTED. ADR 0001
names that exact race as one of the three reasons this project chose PostgreSQL, so the
transaction the decision promised was never actually taken.

It is now real rather than theoretical. Simulating two concurrent attempts from a user
holding two active bookings: **without** the lock both insert and the user ends with four
active bookings; **with** it, one inserts, the other is refused 409, and the user ends with
three. `ensure_room_for_another_booking` locks the owner's row with `SELECT ... FOR UPDATE`
before counting, so everything that changes one owner's booking count is serialised. The
lock is on the user rather than on bookings because the thing being protected is a property
of the user, and a row that does not exist yet cannot be locked.

Note that a burst of ten simultaneous HTTP requests did **not** reproduce the race — the
window is narrow. Absence of a reproduction over HTTP was not evidence of safety.
