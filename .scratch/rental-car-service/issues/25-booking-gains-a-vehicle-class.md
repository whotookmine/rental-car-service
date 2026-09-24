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
- [ ] The booking's foreign key to the vehicle class is `ON DELETE RESTRICT`, matching
      ticket 23: removing a class that bookings point at must answer 409, never cascade

## Hand-off note

**This ticket is the only thing Garfield waits on until integration.** His tickets 29
(pickup branch on a booking) and 33 (money) both need a booking that names a vehicle class.
He can do 28, 30, 31 and 36 without it, so there is roughly four tickets of slack — but
tell him the moment this merges rather than at the end of the phase.

It also opens the shared file. From here, `app/bookings/` is edited by both of us: Time in
25, 26 and 41, Garfield in 29, 32 and 37. Each of those adds a column and a rule to the
same model and router. Land them one at a time and pull before starting, or the merges get
ugly.
