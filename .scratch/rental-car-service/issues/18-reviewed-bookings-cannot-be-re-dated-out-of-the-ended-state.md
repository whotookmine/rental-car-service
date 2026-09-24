# 18 — Reviewed bookings cannot be re-dated out of the ended state

**What to build:** A booking that already carries a review cannot have its dates moved so
that its rental period is no longer over. Without this, a review ends up describing a
rental still in progress, which contradicts the premise that reviews only ever describe
finished rentals. Reachable by an owner and an admin alike, so the rule belongs to the
booking rather than to either role.

**Blocked by:** 15

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] Extending a reviewed booking so that its rental period would no longer be ended is
      refused as a conflict
- [x] The rule applies to the booking's owner and to an admin identically
- [x] Re-dating a reviewed booking within the past, so that it remains ended, is still
      permitted
- [x] Re-dating a booking with no review into the future is unaffected
- [x] Deleting the review frees the booking to be re-dated normally

## Notes

- The rule lives in `app/bookings/rules.py` and is called from the single edit path, so it
  applies to an owner and an admin through the same code rather than being written twice.
  Verified from both sides: the owner and the admin each get 409 on the same booking, and
  both can still re-date it within the past.
- **The boundary is the sharp part.** "No longer ended" means `end_date >= today()`,
  because a rental period ending today has not ended — the same boundary the active-booking
  cap uses. So moving a reviewed booking to end **today** is refused, and moving it to end
  **yesterday** is allowed. An implementation using `> today()` would pass every other test
  in this ticket and be wrong only on that one day.
- A booking with no review is untouched: owner and admin can both still extend it into the
  future, so ticket 12 has not regressed.
- Deleting the review lifts the block immediately; the same extension then succeeds.

### Ordering, decided deliberately

An edit can break this rule and the cap at once. The review refusal is reported first,
because it is **absolute** — no amount of freeing slots will make a reviewed booking
movable into the future — whereas the cap clears on its own as rental periods end. Telling
the caller the permanent blocker is more use than telling them the transient one. Verified
with an owner holding three active bookings plus a reviewed ended one.

Malformed dates still answer 422 ahead of either 409, since validation runs before the
handler. `docs/SPEC.md` records all of this.

### Found while testing

The first run returned 500 on every request: the rule was called but its import had not
been added, because the router's import line was not the shape the edit assumed. Caught
because the response was a 500 rather than the expected 409 — a reminder that a rule which
raises is not the same as a rule that is wired in.

