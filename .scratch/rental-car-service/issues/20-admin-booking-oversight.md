# 20 — Admin booking oversight

**What to build:** An admin can see and act on every booking in the system, to support
registered users and correct mistakes. Scope widens by role on the same routes rather than
through a separate admin namespace, so the ownership rule lives in one place and cannot
drift between two copies. An admin has wider reach, not weaker rules: their edits are
validated exactly as an owner's are.

**Blocked by:** 12, 13

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] Listing bookings returns every booking in the system when the caller is an admin,
      and only the caller's own when they are a registered user — the same route for both
- [x] An admin fetches any single booking by identifier
- [x] An admin changes the dates on any booking
- [x] An admin deletes any booking
- [x] Admin edits are validated by exactly the same rules an owner faces, including the
      thirty-day maximum and the three-active-booking cap measured against the booking's
      owner
- [x] A consequence to accept rather than work around: an admin cannot extend an ended
      booking for a user who already holds three active ones, even to correct a genuine
      error
- [x] An admin cannot change which provider a booking is with
- [x] Admins do not hold bookings of their own; an admin attempting to create one is
      refused

## Notes

- Scope widens by role on the same routes; there is no admin namespace. `GET /bookings`
  returns the caller's own bookings, or every booking when the caller is an admin, decided
  from the role and applied in the query so no parameter can widen it. The single-booking
  lookup became `get_visible_booking_or_404`, which is the one place the ownership rule
  lives for fetching, re-dating and deleting alike.
- Verified live with three actors: Alice sees only hers, Bob only his, the admin sees both.
  The admin fetched, re-dated and deleted Bob's booking, and Bob's record showed the
  admin's new dates afterwards.
- A registered user reaching for another user's booking still answers 404 — widening the
  admin's scope did not widen anyone else's.
- Admin edits run the same validation: a 31-day period, a reversed range and an attempt to
  change the provider are all 422, and an admin creating a booking of their own is still
  403.

### The cap is measured against the owner, and it was worth proving

The discriminating test is an admin who holds **zero** bookings editing a booking whose
owner holds three. If the cap were measured against the caller the edit would succeed. It
is refused with 409, and it succeeds once one of the owner's rental periods is ended. That
is the consequence this ticket asks us to accept rather than work around: an admin cannot
extend an ended booking for a user already at the limit, even to correct a genuine error.

Editing that same ended booking while leaving it ended still works, because it occupies no
slot.

### Fixed while testing

The refusal message read "**You** already hold 3 active bookings" regardless of who was
asking, so an admin holding none was told the bookings were theirs. The rule was right and
the sentence was not. The message is now chosen by whether the caller owns the booking:
owners are addressed directly, and an admin is told about the booking's owner instead.
