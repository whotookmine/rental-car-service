# 46 — An expired claim passes to the next in the queue

**What to build:** The requirement says the claim window comes "before offering it to the
next person in the queue", so expiry is not the end of the story — it hands on. This
closes the loop that makes a waitlist a queue rather than a lottery.

**Blocked by:** 45

**Owner:** Time

**Status:** ready-for-agent

- [ ] An expired claim is offered to the next entry whose date range the capacity
      satisfies, and that person is notified
- [ ] The expired holder loses their place rather than returning to the front
- [ ] A declined claim passes on the same way as an expired one
- [ ] When nobody is left in the queue, the capacity simply becomes available again
- [ ] Passing on is evaluated lazily, when the queue is next touched, so a queue nobody
      reads for a week still behaves correctly when it is finally read
- [ ] A chain works end to end: three people queue, the first lets the claim expire, the
      second declines, the third is offered it and books it
- [ ] Time is judged in the business timezone, like every other rule
- [ ] The whole pass-on happens under the same lock, so a claim cannot expire into two
      people's hands at once

## Hand-off note

With ticket 41, this is the second and last thing Garfield waits on, for the same reason:
ticket 47 seeds a waiting queue, which cannot exist until the queue behaves correctly.
