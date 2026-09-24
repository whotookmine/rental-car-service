# 29 — Bookings name a pickup branch

**What to build:** A booking records where the car is collected. Until a booking has a
pickup branch there is nothing for a drop-off branch to differ from, so this precedes
one-way rentals.

**Blocked by:** 28, 25

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] Creating a booking requires a pickup branch, and it must belong to the provider in
      the path
- [ ] A branch belonging to a different provider is refused
- [ ] The pickup branch appears on every booking response
- [ ] The pickup branch is fixed at creation, like the provider and the vehicle class
- [ ] Every existing booking rule still holds, including capacity from ticket 26
- [ ] Existing bookings are migrated to their provider's first branch, and the migration
      says so

## Coordination note

Blocked on Time's ticket 25, which adds the vehicle class to a booking. You can do 28, 30,
31 and 36 first without waiting.

This is also where you start editing `app/bookings/`, which Time is editing in 25, 26 and
41. Pull before you start and land your booking-touching tickets (29, 32, 37) one at a
time.
