# 28 — Branches under a provider

**What to build:** A provider stops being a single address and becomes a business with
places you collect a car from. One-way rentals and delivery radii are both defined between
or around branches, so neither requirement is expressible until branches exist.

**Blocked by:** None — can start immediately

**Owner:** Garfield

**Status:** done — verified against a running app and a real database

- [x] An admin creates a branch under a provider, with a name, address and telephone
- [x] An admin edits and removes a branch
- [x] Any authenticated user lists a provider's branches and fetches one by identifier
- [x] A registered user is refused 403 on every write
- [x] A provider always has at least one branch; removing the last one is refused
- [x] Removing a branch referenced by a booking is refused rather than cascading
- [x] The provider's existing single address becomes its first branch in the migration,
      so no provider is left without one and no address is lost
- [x] The migration states what it did with the old column, and whether the provider keeps
      an address of its own or now reads it from the branch

## Notes

New package `app/branches/` with model, schemas, dependencies, and router.

Routes:
- `GET /providers/{id}/branches` — list, any authenticated
- `POST /providers/{id}/branches` — create, admin only
- `GET /branches/{id}` — fetch, any authenticated
- `PATCH /branches/{id}` — edit, admin only
- `DELETE /branches/{id}` — remove, admin only

**Provider keeps its own address column.** The migration does not drop `providers.address`
or `providers.telephone`. Those columns remain the general business contact details exposed
in provider catalogue responses and booking read shapes. A branch address is the specific
pickup location a booking will name from ticket 29 onwards.

**Migration** (`cb0b6c819227`) creates the `branches` table and inserts one "Main Branch"
per existing provider using `INSERT INTO branches ... SELECT ... FROM providers`. All
providers have at least one branch from the moment the migration applies.

**Booking reference guard (criterion 6)** is present in the delete handler as an
`IntegrityError` catch. No booking references a branch yet (ticket 29 adds that FK with
`ON DELETE RESTRICT`), so the guard cannot be exercised now. It is there so the route
does not answer 500 once that column lands.
