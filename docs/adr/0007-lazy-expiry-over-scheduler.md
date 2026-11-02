# Lazy claim expiry over a background scheduler

When a waitlist claim is not converted or declined within the claim window
(`CLAIM_WINDOW_MINUTES`, default 60), the car it holds passes to the next eligible person
in the queue. That expiry could be driven by a background job that runs on a timer, or it
could be judged whenever the queue is next touched. This project uses the latter.

**No scheduler is in scope.** Adding one would mean a persistent process or cron job, a
mechanism to restart it, and a way to observe whether it ran. None of those exist in this
project, and building them to serve one use case would be a significant addition.

**Liveness, not correctness.** A claim past its expiry is never honoured — `state` is
computed from timestamps on every read, so an expired claim reads as `expired` and cannot
be converted, regardless of whether anything has run. The only cost of lazy expiry is
latency: a car held by a lapsed claim is not offered to the next person until someone reads
or writes the queue. For a demo-scale service this is acceptable.

**Settling on touch.** `GET /waitlist_entries`, joining, converting, declining, and
deleting a booking all settle the queues they affect before reporting. A GET with a write
effect is surprising, and this ADR exists so a future reader finds the explanation rather
than discovering the behaviour and wondering whether it is a bug.

**Verified.** Backdating a claim's `claim_expires_at` to the past and then reading the
queue produces `state: expired` and offers the capacity to the next entry — with nothing
having run in between. See the verification notes in the ticket-46 Notes section.

## Consequences

- If nobody reads or writes a queue for an extended period, lapsed claims are not settled
  until the first access. The capacity they held is not lost — it becomes bookable by
  anyone — but the next person in the queue is not notified until the queue is touched.
- A background scheduler could be introduced later without changing the correctness model,
  only the latency. The lazy path remains correct either way, because liveness is
  always computed.
