# 16 — Review editing and deletion

**What to build:** The author of a review can correct a mistake, change their mind, or
withdraw the opinion entirely — without having to destroy the booking to do it. The
requirements never grant this; it is granted deliberately, because deleting the booking
already gives users a destructive route to the same outcome, and offering the direct route
is better for the data.

**Blocked by:** 15

**Status:** ready-for-agent

- [ ] An author changes the rating and comment on their own review
- [ ] Rating validation on edit matches creation
- [ ] An author deletes their own review
- [ ] Deleting a review leaves its booking intact
- [ ] A booking whose review was deleted becomes reviewable again
- [ ] The booking a review belongs to cannot be changed; a review can never be moved to a
      different booking
- [ ] Editing or deleting another user's review reports not-found, not forbidden
- [ ] An unauthenticated caller is refused
