# 04 — Admin provisioning

**What to build:** A way to create an admin account, which deliberately does not exist
through the API. Without this, every admin-gated capability in the system is untestable,
so it lands early rather than alongside the rest of the demo data.

**Blocked by:** 02

**Owner:** Garfield

**Status:** done — merged to main, reviewed. All criteria verified against a running API.

- [x] A command creates an admin account with known credentials
- [x] The command is documented so that anyone setting the project up can run it
- [x] No API route can create an admin, promote a registered user, or change any user's
      role
- [x] The created admin can log in through the normal login endpoint and receives a token
      like any other user
- [x] A reusable guard distinguishes admins from registered users and is available to
      every later endpoint
- [x] Running the command twice does not create a duplicate admin

## Notes

- Verified live: the command creates an admin, running it twice leaves the existing
  account untouched, the admin logs in through the normal login endpoint, and no API
  route creates or promotes one.
- `require_admin` lives in the auth package alongside `get_current_user` and returns 403,
  not 404. The 404-over-403 rule applies to bookings, where a 403 would reveal that
  someone else's booking exists; admin-only provider routes have nothing to hide.
- Fixed after review: the command applied no password rule at all, so the most privileged
  account in the service could be given a weaker password than any ordinary user, and an
  over-long one reached bcrypt and raised a traceback. Both now go through the shared
  `validate_password` rule that registration uses.
- Still outstanding, belongs to ticket 14: the default credentials are committed and
  nothing stops the command running when `ENV=production`. The seed script owes that guard
  and this command should share it.

### Corrected after audit

The docstring in `app/auth/models.py` claimed admins exist "only because the seed command
created them". There is no seed command yet — that is ticket 14 — and admins come from
`app.create_admin`. The comment now says so, since it was misdirecting a reader about the
only privileged-account path in the service.
