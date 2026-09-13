# Providers are retired, never deleted

An admin deleting a provider must not destroy the bookings and reviews that reference it,
because that is one party's catalogue housekeeping silently erasing another party's
rental history. `DELETE /providers/{id}` therefore marks the provider retired rather than
removing the row: it stops accepting new bookings and drops out of the provider list,
while existing bookings continue, remain editable by their owners, and remain reviewable.
Retiring is reversible by an admin. No route deletes a provider row.

## Considered Options

Blocking deletion outright (`ON DELETE RESTRICT`) was rejected because a provider that
goes out of business could then never be removed from the bookable list, since its
historical bookings pin it in place forever. Cascading deletion was rejected outright.

## Consequences

- Every query that lists bookable providers must filter out retired ones, while direct
  fetches by id must not, so that users can still see who they booked with.
- `DELETE` is not literally destructive on this resource, which deviates from strict REST
  semantics. It was kept as the verb because it is what an admin and a test suite will
  reach for.
