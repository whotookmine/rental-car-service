# 12 — Booking re-dating

**What to build:** A registered user adjusts their plans by changing a booking's dates,
including extending one that is already underway. Which provider the booking is with can
never change, so that every booking keeps reflecting the company actually reserved with —
this is what keeps a review attached to the right provider.

**Blocked by:** 09

**Status:** ready-for-agent

- [ ] An owner changes the start and end dates of their own booking
- [ ] The same rules as creation apply: end on or after start, and at most thirty days
- [ ] Unlike creation, a start date in the past is permitted, so that a booking already
      underway can be extended and history can be corrected
- [ ] The three-active-booking cap is re-checked, so a user cannot edit their way past it
- [ ] The provider cannot be changed; an attempt to change it is refused or ignored, never
      silently applied
- [ ] Editing another user's booking reports not-found, not forbidden
- [ ] Editing a booking that does not exist reports not-found
- [ ] An unauthenticated caller is refused
