# 24 — Vehicle units

**What to build:** The individual cars a provider actually owns, each belonging to one
vehicle class. Capacity is a count of these, and maintenance blackouts in ticket 39 are
scheduled against one of them, so both later features need units rather than just classes.

**Blocked by:** 23

**Owner:** Time

**Status:** ready-for-agent

- [ ] An admin adds a vehicle to a class, with a registration or plate identifier
- [ ] An admin edits and removes a vehicle
- [ ] The plate identifier is unique across the system and the duplicate is a conflict
- [ ] A vehicle belongs to exactly one class and cannot be moved to another provider's class
- [ ] Any authenticated user can see how many vehicles a class has, without necessarily
      seeing each plate
- [ ] A registered user is refused 403 on every write
- [ ] Removing a vehicle that has a blackout window or is otherwise referenced is refused
      rather than cascading
- [ ] Adding vehicles raises that class's capacity, which ticket 26 then enforces
- [ ] The vehicle's foreign key to its class is `ON DELETE RESTRICT`, so ticket 23's
      "vehicle class is in use" refusal becomes real rather than theoretical; verify that
      removing a class that has vehicles answers 409
