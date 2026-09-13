# 02 — User registration and token issuance

**What to build:** A visitor becomes a registered user by giving their name, telephone
number, email, and password, and receives an access token in the same response so they
can start using the system without a separate login step. Nobody can make themselves an
admin on the way in.

**Blocked by:** 01

**Owner:** Time

**Status:** done — merged to main. All criteria verified against a running API.

- [x] Registration accepts name, telephone number, email, and password and creates a
      registered user
- [x] The response carries an access token valid for the configured lifetime
- [x] Email is unique; registering an email already in use is rejected
- [x] Email is treated case-insensitively and stored lowercased, so it cannot be
      duplicated by changing case
- [x] Passwords shorter than eight characters are rejected; no complexity rules are
      applied
- [x] Passwords are hashed with bcrypt and never stored in plain text
- [x] No response anywhere in the system contains a password or password hash
- [x] Telephone number validation is loose: non-empty, permitting digits, spaces, hyphens
      and a leading plus
- [x] Role defaults to user and cannot be set, overridden, or influenced by the request
      body, whatever a caller sends
- [x] Malformed input is rejected as unprocessable

## Notes

- `bcrypt` is used directly rather than through passlib, as `docs/SPEC.md` originally
  said. passlib 1.7.4 (last released 2020) fails against bcrypt 5.x. `docs/SPEC.md` has
  been corrected to match.
- Passwords are also capped at 72 bytes, which is bcrypt's own limit rather than a policy
  choice. Over-long passwords are rejected as unprocessable instead of reaching bcrypt and
  raising.
- Found and fixed while verifying the "no response contains a password" criterion:
  Pydantic echoes the rejected value in validation errors, so a short or over-long
  password was being returned in the 422 body, as was the whole request body when some
  other field was missing. A validation error handler now redacts password values.
- Unknown fields on registration are rejected rather than ignored, so an attempt to send
  `"role": "admin"` fails with 422 instead of appearing to succeed.
