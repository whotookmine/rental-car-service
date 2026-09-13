# 07 — Provider retirement and reinstatement

**What to build:** An admin takes a provider that has stopped trading out of circulation
without destroying anything, and can bring it back. Per the architecture decision, the
delete verb retires rather than removes: no route ever deletes a provider row, because
doing so would erase the rental history of everyone who ever booked with it.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] An admin retires a provider using the delete verb; the record survives
- [ ] The response makes clear that the provider was retired, not removed
- [ ] Retired providers are excluded from the provider list by default
- [ ] A retired provider is still fetchable directly by identifier, by any authenticated
      user, so people can see who they booked with
- [ ] A provider's response indicates whether it is retired
- [ ] An admin can request that the list include retired providers; a registered user
      making the same request does not receive them
- [ ] An admin reinstates a retired provider, returning it to the list
- [ ] A registered user attempting to retire or reinstate a provider is refused as
      forbidden
- [ ] Retiring a provider leaves every booking and review referencing it untouched
