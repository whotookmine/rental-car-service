# 23 — Vehicle class catalogue

**What to build:** A provider's catalogue of what kinds of car it rents — economy, SUV,
van and so on. This is the thing a customer books and the thing a waitlist queues for.
It exists because the second round of requirements talks about a "fully-booked vehicle
class", and until now the system modelled no vehicles at all.

**Blocked by:** None — can start immediately

**Owner:** Time

**Status:** ready-for-agent

- [ ] An admin creates a vehicle class under a provider, with a name and a description
- [ ] An admin edits and removes a vehicle class
- [ ] A class belongs to exactly one provider and cannot be moved between providers
- [ ] Any authenticated user lists a provider's vehicle classes
- [ ] A registered user is refused 403 on create, edit and remove
- [ ] An unauthenticated caller is refused 401
- [ ] Class names are unique within a provider, and the duplicate is refused as a conflict
- [ ] Removing a class that has vehicles or bookings against it is refused rather than
      cascading, so history is never destroyed by catalogue housekeeping
- [ ] Classes belonging to a retired provider are still fetchable, matching how retired
      providers themselves behave
