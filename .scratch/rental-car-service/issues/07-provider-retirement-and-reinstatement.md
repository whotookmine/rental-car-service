# 07 — Provider retirement and reinstatement

**What to build:** An admin takes a provider that has stopped trading out of circulation
without destroying anything, and can bring it back. Per the architecture decision, the
delete verb retires rather than removes: no route ever deletes a provider row, because
doing so would erase the rental history of everyone who ever booked with it.

**Blocked by:** 06

**Owner:** Garfield

**Status:** done — merged to main, reviewed. All criteria verified against a running API.

- [x] An admin retires a provider using the delete verb; the record survives
- [x] The response makes clear that the provider was retired, not removed
- [x] Retired providers are excluded from the provider list by default
- [x] A retired provider is still fetchable directly by identifier, by any authenticated
      user, so people can see who they booked with
- [x] A provider's response indicates whether it is retired
- [x] An admin can request that the list include retired providers; a registered user
      making the same request does not receive them
- [x] An admin reinstates a retired provider, returning it to the list
- [x] A registered user attempting to retire or reinstate a provider is refused as
      forbidden
- [x] Retiring a provider leaves every booking and review referencing it untouched

## Notes

- Verified live: delete retires rather than removes, the record survives and is still
  fetchable by identifier, the list excludes it, reinstating returns it, and a registered
  user is refused 403 on retire and reinstate alike.
- The security-critical case passes: a registered user who sends `include_retired=true`
  is still given only active providers. The filter checks the caller's role, not just the
  parameter.
- Retiring an already-retired provider succeeds and changes nothing, so the operation is
  idempotent.
- Existing bookings and reviews are untouched by retirement. Nothing references a provider
  yet, so that will be worth re-checking when bookings land in ticket 08.
