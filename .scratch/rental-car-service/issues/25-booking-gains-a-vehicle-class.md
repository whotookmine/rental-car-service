# 25 — Bookings name a vehicle class

**What to build:** A booking stops being "a period with a provider" and becomes "a period
with a provider, for a kind of car". Every existing booking rule keeps working; the
booking simply carries more. This is the change that makes capacity, blackouts and the
waitlist expressible at all.

**Blocked by:** 24

**Owner:** Time

**Status:** ready-for-agent

- [ ] Creating a booking requires a vehicle class, and the class must belong to the
      provider in the path
- [ ] A class from a different provider is refused
- [ ] A booking that names no class, or a class that does not exist, is refused
- [ ] The class appears on every booking response, alongside the provider
- [ ] The class is fixed at creation and cannot be changed by re-dating, for the same
      reason the provider cannot: a review must keep describing what was actually rented
- [ ] Every rule from tickets 08 to 20 still holds unchanged: date shape, the thirty-day
      maximum, no past-dated creation, the three-active cap, ownership scoping, admin
      oversight, and the reviewed-booking rule
- [ ] Existing bookings are migrated rather than destroyed; the migration states what
      class historical rows are given and why
