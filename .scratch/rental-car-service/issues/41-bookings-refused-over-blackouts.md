# 41 — Bookings overlapping a blackout are refused

**What to build:** The enforcement half of maintenance. Availability reporting a vehicle as
gone is not enough; a booking that would consume it has to be refused, including when the
window is scheduled after the booking was made.

**Blocked by:** 40, 26

**Owner:** Time

**Status:** ready-for-agent

- [ ] A booking is refused as a conflict when the class has no vehicle free of blackouts
      for the whole rental period
- [ ] The refusal distinguishes "fully booked" from "unavailable for maintenance", so the
      user knows whether waiting will help
- [ ] Re-dating a booking onto days where the class is blacked out is refused too, for
      owner and admin alike
- [ ] Capacity counts vehicles, blackouts and existing bookings together: two vehicles, one
      blacked out, one already booked means the class is full
- [ ] Decide and state what happens to a booking that already exists when an admin
      schedules a blackout over it — refused, allowed, or allowed with the booking flagged.
      Whichever is chosen, an existing booking must not silently vanish
- [ ] The check runs under the same lock as the capacity count, so a blackout and a booking
      cannot race
