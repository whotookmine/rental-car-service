# 36 — Delivery radius per branch

**What to build:** How far a branch is willing to bring a car. The requirement validates a
delivery address against "the provider's delivery radius", so the radius has to be recorded
before an address can be judged against it.

**Blocked by:** 28

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] An admin sets a delivery radius in kilometres on a branch
- [ ] A branch with no radius set does not offer delivery at all, which is different from
      a radius of zero
- [ ] A negative radius is refused as unprocessable
- [ ] An admin can clear a radius, withdrawing delivery from that branch
- [ ] Any authenticated user can see whether a branch offers delivery and how far
- [ ] A registered user is refused 403 on every write
- [ ] Withdrawing delivery leaves existing bookings that used it untouched
