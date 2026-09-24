# 33 — Money foundation

**What to build:** The system's first notion of price. Until now nothing cost anything;
the second round of requirements computes a relocation fee and a delivery charge and adds
them to a quotation, so money has to exist before either can.

This is the largest single addition of the round and the easiest to get subtly wrong, so
it lands on its own rather than inside a feature.

**Blocked by:** 25

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] Amounts are stored as exact decimals, never as floating point: money that rounds
      differently on different machines is a defect that surfaces only in totals
- [ ] A single currency, named in configuration rather than hardcoded, since the brief
      describes one market
- [ ] A vehicle class carries a daily rate, set and edited by an admin
- [ ] A negative or non-numeric rate is refused as unprocessable
- [ ] A rate of zero is allowed and means free, which is different from having no rate
- [ ] A class with no rate set is reported as unpriced rather than as costing nothing
- [ ] Rounding is defined once, stated in `docs/SPEC.md`, and applied in one place
- [ ] Amounts appear in responses in a single consistent shape, decided here and used by
      every later ticket
