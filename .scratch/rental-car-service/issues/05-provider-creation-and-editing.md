# 05 — Provider creation and editing

**What to build:** An admin builds up the catalogue of rental car providers, adding each
with its name, address, and telephone number, and correcting those details later.
Registered users cannot touch the catalogue. The requirements never say who creates
providers; this fills that gap, since an admin with power over bookings but none over
what those bookings point at would be a strange figure.

**Blocked by:** 03, 04

**Status:** ready-for-agent

- [ ] An admin creates a provider with name, address, and telephone number
- [ ] An admin edits any of those details on an existing provider
- [ ] A registered user attempting to create or edit a provider is refused as forbidden
- [ ] An unauthenticated caller attempting either is refused as unauthenticated
- [ ] Missing or empty required fields are rejected as unprocessable
- [ ] Editing a provider that does not exist reports not-found
