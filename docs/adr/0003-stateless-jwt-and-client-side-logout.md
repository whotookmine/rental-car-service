# Stateless JWT with client-side logout

Authentication issues a stateless JWT valid for 60 minutes
(`ACCESS_TOKEN_EXPIRE_MINUTES`), with no refresh token. `POST /auth/logout` exists to
satisfy the requirement that a registered user can log out, but it invalidates nothing
server-side: the client discards the token and the issued token remains valid until it
expires. This is deliberate, not an oversight. A revocation denylist checked on every
request would reintroduce the per-request database lookup that stateless tokens exist to
avoid, and refresh tokens were rejected because an unrevocable refresh token is strictly
worse than none.

## Consequences

- The residual exposure window for a stolen token is up to 60 minutes, which is the
  entire mitigation behind the confidentiality requirement. Raising the expiry weakens
  that argument, so the value should stay small.
- If revocation is ever genuinely needed, the cheapest path is opaque server-side
  sessions rather than a JWT denylist.
