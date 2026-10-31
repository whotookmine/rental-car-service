# 36 — Delivery radius per branch

**What to build:** How far a branch is willing to bring a car. The requirement validates a
delivery address against "the provider's delivery radius", so the radius has to be recorded
before an address can be judged against it.

**Blocked by:** 28

**Owner:** Garfield

**Status:** done

- [x] An admin sets a delivery radius in kilometres on a branch
- [x] A branch with no radius set does not offer delivery at all, which is different from
      a radius of zero
- [x] A negative radius is refused as unprocessable
- [x] An admin can clear a radius, withdrawing delivery from that branch
- [x] Any authenticated user can see whether a branch offers delivery and how far
- [x] A registered user is refused 403 on every write
- [x] Withdrawing delivery leaves existing bookings that used it untouched

## Notes

- `delivery_radius_km` added as nullable integer on `branches` (migration `abc1def23456`).
  NULL = no delivery; 0 = delivery from branch location only; positive = radius in km.
- Two new admin-only routes: `PUT /branches/{id}/delivery-radius` (body: `{"kilometres": N}`)
  and `DELETE /branches/{id}/delivery-radius` (204). Existing read routes (`GET /branches/{id}`
  and `GET /providers/{id}/branches`) already expose the field via `BranchRead`.
- Ticket 37 (delivery address on booking) is the next downstream consumer of this field.
