# 04 — Admin provisioning

**What to build:** A way to create an admin account, which deliberately does not exist
through the API. Without this, every admin-gated capability in the system is untestable,
so it lands early rather than alongside the rest of the demo data.

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] A command creates an admin account with known credentials
- [ ] The command is documented so that anyone setting the project up can run it
- [ ] No API route can create an admin, promote a registered user, or change any user's
      role
- [ ] The created admin can log in through the normal login endpoint and receives a token
      like any other user
- [ ] A reusable guard distinguishes admins from registered users and is available to
      every later endpoint
- [ ] Running the command twice does not create a duplicate admin
