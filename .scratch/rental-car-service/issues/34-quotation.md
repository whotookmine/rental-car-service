# 34 — Quotation

**What to build:** What a proposed booking would cost, itemised, before anyone commits to
it. The requirements describe fees being "added to the quotation", so the quotation is the
thing they add to and it has to exist first.

**Blocked by:** 33

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] An authenticated user asks what a proposed booking would cost, giving the same
      details a booking needs: provider, class, dates, branches
- [ ] The response itemises the charge rather than giving only a total, so a later fee can
      be added as a line rather than folded invisibly into a number
- [ ] The rental line is the class's daily rate times the length of the rental period,
      counted inclusively the same way every other rule counts it
- [ ] The total is the sum of the lines, rounded once, at the end
- [ ] A quotation for an unpriced class reports that it cannot be priced rather than
      returning zero
- [ ] The same validation as booking applies: date shape, thirty-day maximum, class and
      branches belonging to the provider
- [ ] A quotation reserves nothing and changes nothing; asking twice gives the same answer
- [ ] An unauthenticated caller is refused
