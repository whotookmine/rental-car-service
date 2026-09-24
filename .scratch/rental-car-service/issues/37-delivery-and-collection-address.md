# 37 — Delivery and collection address on a booking

**What to build:** A registered user asks for the car to be brought to an address and
collected from it afterwards, instead of going to the branch. The address is checked
against the branch's delivery radius, and a booking outside it is refused.

Distance comes from the admin-recorded figures rather than geocoding, so the request
carries a distance from the branch rather than being resolved from the address text. Ticket
48's ADR records why.

**Blocked by:** 36, 29

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] A booking may carry a delivery address and its distance from the pickup branch
- [ ] Omitting delivery is the ordinary case and stays the simplest one
- [ ] A delivery distance beyond the branch's radius is refused as a conflict, naming the
      radius so the user knows by how much
- [ ] Delivery from a branch that offers none is refused
- [ ] A distance exactly equal to the radius is accepted, since the radius is inclusive —
      state the boundary rather than leaving it to be discovered
- [ ] A negative distance, or an address that is blank, is refused as unprocessable
- [ ] Collection is at the same address as delivery unless stated otherwise
- [ ] The delivery details appear on the booking response
