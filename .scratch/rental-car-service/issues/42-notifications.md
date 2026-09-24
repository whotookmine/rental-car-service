# 42 — Notification records

**What to build:** Somewhere for the system to tell a user something, and for the user to
read it. The waitlist has to notify people when inventory is released, and without this
there is nothing for it to notify into.

Records the user polls, not email: SMTP means credentials, deliverability and an external
dependency the brief never asks for, and none of it can be demonstrated in Postman.

**Blocked by:** None — can start immediately

**Owner:** Time

**Status:** ready-for-agent

- [ ] A registered user lists their own notifications, newest first
- [ ] Each notification carries a kind, a message, when it was created, and whether it has
      been read
- [ ] A user marks a notification read
- [ ] A user sees only their own; another user's reports not-found, exactly as bookings do
- [ ] An unauthenticated caller is refused
- [ ] A user with none receives an empty list rather than an error
- [ ] Notifications are created by the system, never by a request: there is no route that
      lets a caller send one, to themselves or to anyone else
- [ ] An admin does not receive or read other users' notifications through this route
