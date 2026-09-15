# 05 — Provider creation and editing

**What to build:** An admin builds up the catalogue of rental car providers, adding each
with its name, address, and telephone number, and correcting those details later.
Registered users cannot touch the catalogue. The requirements never say who creates
providers; this fills that gap, since an admin with power over bookings but none over
what those bookings point at would be a strange figure.

**Blocked by:** 03, 04

**Owner:** Garfield

**Status:** done — merged to main, reviewed. All criteria verified against a running API.

- [x] An admin creates a provider with name, address, and telephone number
- [x] An admin edits any of those details on an existing provider
- [x] A registered user attempting to create or edit a provider is refused as forbidden
- [x] An unauthenticated caller attempting either is refused as unauthenticated
- [x] Missing or empty required fields are rejected as unprocessable
- [x] Editing a provider that does not exist reports not-found

## Notes

- Verified live: an admin creates and edits providers; a registered user is refused with
  403 on both; an unauthenticated caller gets 401; blank or missing fields are 422; and
  editing a provider that does not exist is 404.
- Editing is a PATCH, so a caller sends only the fields they are changing.
- Unknown fields are rejected rather than ignored, which is what stops `is_retired` being
  flipped through the edit route. Retirement has its own route by design.
