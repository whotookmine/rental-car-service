# 34 — Quotation

**What to build:** What a proposed booking would cost, itemised, before anyone commits to
it. The requirements describe fees being "added to the quotation", so the quotation is the
thing they add to and it has to exist first.

**Blocked by:** 33

**Owner:** Garfield

**Status:** done — verified against a running app and a real database

- [x] An authenticated user asks what a proposed booking would cost, giving the same
      details a booking needs: provider, class, dates, branches
- [x] The response itemises the charge rather than giving only a total, so a later fee can
      be added as a line rather than folded invisibly into a number
- [x] The rental line is the class's daily rate times the length of the rental period,
      counted inclusively the same way every other rule counts it
- [x] The total is the sum of the lines, rounded once, at the end
- [x] A quotation for an unpriced class reports that it cannot be priced rather than
      returning zero
- [x] The same validation as booking applies: date shape, thirty-day maximum, class and
      branches belonging to the provider
- [x] A quotation reserves nothing and changes nothing; asking twice gives the same answer
- [x] An unauthenticated caller is refused

## Notes

- New package `app/quotations/` — schemas + router, no model (nothing is persisted).
- `POST /providers/{id}/quotations` reuses `resolve_vehicle_class_for_provider`,
  `resolve_branch_for_provider`, and `ensure_one_way_route_enabled` from
  `app/bookings/rules.py` rather than duplicating the logic.
- Line amounts are exact (`Decimal × int`). `round_amount()` is called only on the total,
  matching the ticket requirement.
- No migration needed.
