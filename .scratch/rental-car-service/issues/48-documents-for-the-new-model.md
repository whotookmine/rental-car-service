# 48 — Documents for the new model

**What to build:** The glossary, the ruleset and the decision record brought in line with a
system that now has vehicles, branches and money. This is a ticket rather than a footnote
because the single most repeated failure on this project has been correct code beside a
document that says something untrue.

**Blocked by:** 47

**Owner:** Time

**Status:** ready-for-agent

- [ ] `CONTEXT.md` gains Vehicle Class, Vehicle, Branch, Blackout Window, Waitlist Entry,
      Claim, Quotation and Notification, each with an `_Avoid_` list
- [ ] `CONTEXT.md` no longer says individual vehicles are not modelled, and Booking's
      definition reflects that it now names a class and branches
- [ ] **An ADR superseding the no-Car decision.** The original model deliberately had no
      vehicle entity because the first brief never mentioned one; the second round makes
      that untenable. A future reader must find the reversal explained rather than a
      contradiction
- [ ] **An ADR for admin-recorded distances over geocoding**, recording that an external
      mapping API was rejected for its keys, quotas, failure modes and cost
- [ ] **An ADR for lazy expiry over a scheduler**, recording that claim windows expire when
      the queue is next touched rather than through a background job
- [ ] `docs/SPEC.md` covers every new route, rule, boundary and status code, including the
      capacity rule, the blackout boundary, the delivery radius boundary, the tier
      boundaries, and the ordering between the new conflicts and the existing ones
- [ ] `docs/SPEC.md` states the money rules once: currency, rounding, where amounts are
      exact, and the response shape for an amount
- [ ] No avoided vocabulary anywhere in code, routes, responses or documents
