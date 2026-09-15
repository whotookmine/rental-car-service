# 06 — Provider browsing

**What to build:** A registered user sees which providers they can rent from, with enough
detail to judge whether one is convenient, and can look up a single provider directly.
Average ratings are not part of this ticket — no reviews exist yet.

**Blocked by:** 05

**Owner:** Garfield

**Status:** done — merged to main, reviewed. All criteria verified against a running API.

- [x] Any authenticated user lists all providers
- [x] Each entry carries the provider's identifier, name, address, and telephone number
- [x] Any authenticated user fetches a single provider by identifier
- [x] Fetching a provider that does not exist reports not-found
- [x] An unauthenticated caller is refused

## Notes

- Verified live: any authenticated user lists providers and fetches one by identifier;
  a missing provider is 404; an unauthenticated caller is refused on both routes.
- Average rating and review count are deliberately absent. They arrive with ticket 19,
  once reviews exist.
