# 18 — Reviewed bookings cannot be re-dated out of the ended state

**What to build:** A booking that already carries a review cannot have its dates moved so
that its rental period is no longer over. Without this, a review ends up describing a
rental still in progress, which contradicts the premise that reviews only ever describe
finished rentals. Reachable by an owner and an admin alike, so the rule belongs to the
booking rather than to either role.

**Blocked by:** 15

**Status:** ready-for-agent

- [ ] Extending a reviewed booking so that its rental period would no longer be ended is
      refused as a conflict
- [ ] The rule applies to the booking's owner and to an admin identically
- [ ] Re-dating a reviewed booking within the past, so that it remains ended, is still
      permitted
- [ ] Re-dating a booking with no review into the future is unaffected
- [ ] Deleting the review frees the booking to be re-dated normally
