# 45 — The exclusive claim window

**What to build:** When capacity is offered to someone on the waitlist, it is held for them
alone for a limited time. The requirement calls it a time-limited exclusive claim, so two
things must both be true: nobody else can take it during the window, and it does not last
forever.

**Blocked by:** 44, 42

**Owner:** Time

**Status:** ready-for-agent

- [ ] An offer creates a claim with an expiry, and the holder is notified through ticket 42
- [ ] The claim's duration is configuration, not a hardcoded number, and is stated in
      `docs/SPEC.md`
- [ ] While a claim is live, the vehicle it holds is not available to anyone else: another
      user booking that class for those dates is refused as full, even though a vehicle is
      physically free
- [ ] The claim holder converts it into a booking, which succeeds despite the class
      appearing full to everyone else
- [ ] Converting a claim consumes it; the same claim cannot be used twice
- [ ] The holder may decline, which releases the capacity immediately rather than waiting
      for expiry
- [ ] A claim belonging to another user reports not-found
- [ ] Expiry is judged when the queue is next read or written, not by a background job:
      there is no scheduler in this project, and a claim that has passed its expiry must
      never be honoured even if nothing has touched the queue since
