# 02 — User registration and token issuance

**What to build:** A visitor becomes a registered user by giving their name, telephone
number, email, and password, and receives an access token in the same response so they
can start using the system without a separate login step. Nobody can make themselves an
admin on the way in.

**Blocked by:** 01

**Owner:** Time

**Status:** ready-for-agent

- [ ] Registration accepts name, telephone number, email, and password and creates a
      registered user
- [ ] The response carries an access token valid for the configured lifetime
- [ ] Email is unique; registering an email already in use is rejected
- [ ] Email is treated case-insensitively and stored lowercased, so it cannot be
      duplicated by changing case
- [ ] Passwords shorter than eight characters are rejected; no complexity rules are
      applied
- [ ] Passwords are hashed with bcrypt and never stored in plain text
- [ ] No response anywhere in the system contains a password or password hash
- [ ] Telephone number validation is loose: non-empty, permitting digits, spaces, hyphens
      and a leading plus
- [ ] Role defaults to user and cannot be set, overridden, or influenced by the request
      body, whatever a caller sends
- [ ] Malformed input is rejected as unprocessable
