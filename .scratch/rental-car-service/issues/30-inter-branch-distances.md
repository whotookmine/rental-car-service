# 30 — Inter-branch distances

**What to build:** How far apart two branches are, recorded by an admin rather than
computed from coordinates. Both the relocation fee and the delivery charge are distance
tiers, so distance has to be a number the system knows.

Deliberately not geocoding: an external mapping API means keys, quotas, network failures
and cost, for a number an admin can type once. See the ADR in ticket 48.

**Blocked by:** 28

**Owner:** Garfield

**Status:** done — verified against a running app and a real database

- [x] An admin records the distance in kilometres between two branches of the same provider
- [x] An admin edits and removes a distance
- [x] Distance is symmetric: recording A to B also answers B to A, without a second row
- [x] A distance between branches of different providers is refused
- [x] A distance from a branch to itself is refused, or is always zero and not stored
- [x] Negative or non-numeric distances are refused as unprocessable
- [x] Recording the same pair twice updates rather than duplicating
- [x] Any authenticated user can read a distance; only an admin can write one
- [x] A missing distance is reported as absent rather than assumed to be zero, since a
      zero relocation fee and an unknown one are different things

## Notes

New package `app/branch_distances/`. Model uses composite PK `(from_branch_id, to_branch_id)` with both FKs `ON DELETE CASCADE`. App code always normalises the pair to `(min, max)` before storage and lookup — one row covers both directions.

Routes:
- `PUT /providers/{id}/branch_distances` — upsert (create or update), admin only
- `GET /providers/{id}/branch_distances/{a}/{b}` — fetch, any authenticated
- `DELETE /providers/{id}/branch_distances/{a}/{b}` — admin only

Wrong-provider branch → 409. Nonexistent branch → 422. Same branch → 422 (Pydantic validator). Negative distance → 422 (`gt=0`). Missing pair → 404.

**Bug found and fixed:** reusing a single `Path()` instance as the default for two function parameters causes FastAPI to read both from the same path segment. Fixed by using `Annotated[int, Path(...)]` as a type alias — each parameter gets its own `FieldInfo` instance.
