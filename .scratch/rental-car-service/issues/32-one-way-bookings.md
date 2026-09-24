# 32 — One-way bookings

**What to build:** A registered user drops the car off somewhere other than where they
collected it. The requirement's own condition applies: the combination is refused unless
the provider has enabled one-way service between exactly those branches.

**Blocked by:** 31, 29

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] A booking may name a drop-off branch different from its pickup branch
- [ ] Omitting the drop-off branch means returning to the pickup branch, which is the
      ordinary case and must stay the simplest one
- [ ] A one-way combination the provider has not enabled is refused as a conflict, naming
      the reason
- [ ] The direction matters: pickup A to drop-off B is refused when only B to A is enabled
- [ ] A drop-off branch belonging to a different provider is refused
- [ ] Both branches appear on the booking response
- [ ] The drop-off branch is fixed at creation like the rest of a booking's identity
- [ ] Every existing booking rule still holds, capacity included
