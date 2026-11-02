# 48 — Documents for the new model

**What to build:** The glossary, the ruleset and the decision record brought in line with a
system that now has vehicles, branches and money. This is a ticket rather than a footnote
because the single most repeated failure on this project has been correct code beside a
document that says something untrue.

**Blocked by:** 47

**Owner:** Garfield

**Status:** done

- [x] `CONTEXT.md` gains Vehicle Class, Vehicle, Branch, Blackout Window, Waitlist Entry,
      Claim, Quotation and Notification, each with an `_Avoid_` list
- [x] `CONTEXT.md` no longer says individual vehicles are not modelled, and Booking's
      definition reflects that it now names a class and branches
- [x] **An ADR superseding the no-Car decision.** The original model deliberately had no
      vehicle entity because the first brief never mentioned one; the second round makes
      that untenable. A future reader must find the reversal explained rather than a
      contradiction
- [x] **An ADR for admin-recorded distances over geocoding**, recording that an external
      mapping API was rejected for its keys, quotas, failure modes and cost
- [x] **An ADR for lazy expiry over a scheduler**, recording that claim windows expire when
      the queue is next touched rather than through a background job
- [x] `docs/SPEC.md` covers every new route, rule, boundary and status code, including the
      capacity rule, the blackout boundary, the delivery radius boundary, the tier
      boundaries, and the ordering between the new conflicts and the existing ones
- [x] `docs/SPEC.md` states the money rules once: currency, rounding, where amounts are
      exact, and the response shape for an amount
- [x] No avoided vocabulary anywhere in code, routes, responses or documents

## Notes

**`CONTEXT.md` changes:**
- Booking definition updated to name "a pickup branch and optionally a drop-off branch".
- Added **Branch** (after Provider), **Waitlist Entry** and **Claim** (after Active
  Booking), **Quotation** (before Review). Each carries an `_Avoid_` list.
- Vehicle Class, Vehicle, Blackout Window, and Notification were already present.
- No text in `CONTEXT.md` said "individual vehicles are not modelled"; the Vehicle entry
  had already been added in the round-2 work. The Booking update covers the branch requirement.

**`docs/SPEC.md` changes:**
- Entities section: added Branch row; updated Booking row to mention pickup and drop-off
  branches; updated the opening paragraph to note that Vehicle (ticket 24) and Branch
  (ticket 36) were also added in round 2, not just Vehicle Class.

**New ADRs:**
- `0005-vehicles-supersede-no-car-decision.md` — explains why the no-Car decision was
  reversed (maintenance windows, capacity enforcement, plate administration all require rows).
- `0006-admin-recorded-distances-over-geocoding.md` — geocoding rejected for API keys,
  quotas, failure modes, correctness disagreements, and cost.
- `0007-lazy-expiry-over-scheduler.md` — claim expiry is lazy (judged on touch) because no
  scheduler exists in scope; liveness is always computed so correctness is not affected.

**SPEC.md coverage audit:** All new surfaces were already documented — Branches, Delivery
radius, Delivery on a booking, Branch distances, One-way routes, Money, Vehicle class
surface, Vehicle surface, Blackout window surface, Waitlist surface, Claims, Quotation
surface — as well as every boundary and status code for them. The only gaps were in the
Entities section (Branch missing, Booking missing branches), addressed above.
