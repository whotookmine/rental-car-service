# 44 — Released inventory goes to the queue in order

**What to build:** When a cancellation frees a vehicle, the person who has waited longest
for it gets it. The requirement says strict FIFO, so the order must be the order of joining
and nothing else — not who is quickest to notice, and not who asks first.

**Blocked by:** 43, 41

**Owner:** Time

**Status:** ready-for-agent

- [ ] Deleting a booking that leaves a class no longer full offers the freed capacity to
      the first waitlist entry whose date range it satisfies
- [ ] The order is strictly the order of joining, verified with at least three people in
      one queue
- [ ] An entry whose range the freed capacity does not cover is skipped without losing its
      place for a future release
- [ ] A release that frees capacity no entry wants leaves the queue untouched
- [ ] Two cancellations in quick succession offer to the first and second in the queue
      respectively, never both to the first
- [ ] The offer is made under the same lock as the capacity count, so two simultaneous
      cancellations cannot both offer the same vehicle to the same person
- [ ] Nothing is booked automatically: an offer is an opportunity, and ticket 45 governs
      how it is taken
