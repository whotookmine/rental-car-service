# 37 — Delivery and collection address on a booking

**What to build:** A registered user asks for the car to be brought to an address and
collected from it afterwards, instead of going to the branch. The address is checked
against the branch's delivery radius, and a booking outside it is refused.

Distance comes from the admin-recorded figures rather than geocoding, so the request
carries a distance from the branch rather than being resolved from the address text. Ticket
48's ADR records why.

**Blocked by:** 36, 29

**Owner:** Garfield

**Status:** done

- [x] A booking may carry a delivery address and its distance from the pickup branch
- [x] Omitting delivery is the ordinary case and stays the simplest one
- [x] A delivery distance beyond the branch's radius is refused as a conflict, naming the
      radius so the user knows by how much
- [x] Delivery from a branch that offers none is refused
- [x] A distance exactly equal to the radius is accepted, since the radius is inclusive —
      state the boundary rather than leaving it to be discovered
- [x] A negative distance, or an address that is blank, is refused as unprocessable
- [x] Collection is at the same address as delivery unless stated otherwise
- [x] The delivery details appear on the booking response

## Notes

- Three nullable columns added to `bookings` (migration `bcd2ef34567a`): `delivery_address`,
  `delivery_distance_km`, `collection_address`. All null = no delivery (ordinary case).
- `delivery_address` and `delivery_distance_km` must come as a pair (schema model validator).
- `collection_address` null means collect from the same address as delivery (mirrors the
  dropoff_branch null = round-trip convention).
- Radius validation (409) is in the router, not the schema, because it requires DB state
  (branch radius). Shape validation (422) — negative distance, blank address — is on the schema.
- Migration `bcd2ef34567a` is a merge migration: `down_revision = ('77cc8d1d47ac', 'abc1def23456')`,
  merging our delivery-radius chain with the teammate's waitlist chain that both diverged
  from `1228c9d212a5`.
