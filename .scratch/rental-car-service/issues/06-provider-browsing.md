# 06 — Provider browsing

**What to build:** A registered user sees which providers they can rent from, with enough
detail to judge whether one is convenient, and can look up a single provider directly.
Average ratings are not part of this ticket — no reviews exist yet.

**Blocked by:** 05

**Owner:** Garfield

**Status:** ready-for-agent

- [ ] Any authenticated user lists all providers
- [ ] Each entry carries the provider's identifier, name, address, and telephone number
- [ ] Any authenticated user fetches a single provider by identifier
- [ ] Fetching a provider that does not exist reports not-found
- [ ] An unauthenticated caller is refused
