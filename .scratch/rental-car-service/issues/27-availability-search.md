# 27 — Availability search

**What to build:** A way to ask what can actually be booked before trying to book it.
Given a provider, a date range, and optionally a class, report which classes have a vehicle
free for the whole range and how many. Without this a user can only discover that something
is full by being refused.

**Blocked by:** 26

**Owner:** Time

**Status:** ready-for-agent

- [ ] An authenticated user asks for availability by provider and date range
- [ ] The response lists each vehicle class with the number of vehicles free for the whole
      requested range
- [ ] A class with no free vehicle reports zero rather than being omitted, so a caller can
      tell "full" from "does not exist"
- [ ] The same date rules as booking apply to the query: end on or after start, at most
      thirty days
- [ ] Retired providers are excluded, matching the provider list
- [ ] An unauthenticated caller is refused
- [ ] The answer agrees with what booking actually does: if availability says zero, booking
      is refused, and if it says one, booking succeeds
- [ ] The search is one query rather than one per class
