# 03 — Login, logout, and route protection

**What to build:** A registered user logs in with their email and password to get a
token, and logs out when they are done. Protected parts of the system refuse anyone
without a valid token. Logout is deliberately client-side and invalidates nothing
server-side, as recorded in the architecture decision on stateless tokens.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Login accepts email and password and returns an access token
- [ ] Login is case-insensitive on email, matching registration
- [ ] A wrong password and an unknown email produce the same refusal, so accounts cannot
      be discovered by probing
- [ ] Tokens expire after the configured lifetime, defaulting to sixty minutes
- [ ] A logout endpoint exists and succeeds; it invalidates nothing server-side, and this
      is stated in its API description so it does not read as a defect
- [ ] A reusable guard identifies the calling registered user from the token and is
      available to every later endpoint
- [ ] Requests with a missing, malformed, or expired token are refused as unauthenticated
- [ ] The identity of the caller comes only from the token, never from the request body
      or a query parameter
