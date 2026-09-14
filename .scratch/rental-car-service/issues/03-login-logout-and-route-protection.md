# 03 — Login, logout, and route protection

**What to build:** A registered user logs in with their email and password to get a
token, and logs out when they are done. Protected parts of the system refuse anyone
without a valid token. Logout is deliberately client-side and invalidates nothing
server-side, as recorded in the architecture decision on stateless tokens.

**Blocked by:** 02

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] Login accepts email and password and returns an access token
- [x] Login is case-insensitive on email, matching registration
- [x] A wrong password and an unknown email produce the same refusal, so accounts cannot
      be discovered by probing
- [x] Tokens expire after the configured lifetime, defaulting to sixty minutes
- [x] A logout endpoint exists and succeeds; it invalidates nothing server-side, and this
      is stated in its API description so it does not read as a defect
- [x] A reusable guard identifies the calling registered user from the token and is
      available to every later endpoint
- [x] Requests with a missing, malformed, or expired token are refused as unauthenticated
- [x] The identity of the caller comes only from the token, never from the request body
      or a query parameter

## Notes

- `GET /auth/me` was added beyond the stated criteria. The guard cannot be shown to
  "identify the calling registered user" without an endpoint that reveals who the caller
  is, and the Postman collection in ticket 22 needs one too. `POST /auth/logout` is also
  guarded, which exercises the same dependency.
- `HTTPBearer` is configured with `auto_error=False`. Left to itself it answers a missing
  Authorization header with 403, which says "you may not" when the truth is "I do not know
  who you are". Every authentication failure is now 401 with one message.
- Every failure mode — absent, malformed, expired, forged, or naming a user who no longer
  exists — returns the same 401 body. Verified against a forged signature, an expired
  token signed with the real key, and an `alg: none` token.
- An unknown email spends the same time as a wrong password, by verifying against a
  constant bcrypt digest, so registered addresses cannot be found by timing the refusal.
- Beyond the ticket: `JWT_SECRET_KEY` must now be at least 32 bytes (RFC 7518 for HS256)
  or startup fails. A short signing key is brute-forceable, and a forged token would
  defeat every guard this ticket adds. `docs/SPEC.md` records this.
- Token revocation remains deliberately absent; a token keeps working after logout. This
  is ADR 0003, not a defect, and the endpoint's API description says so.
