# 49 — Postman collection for the new surface

**What to build:** The collection extended to cover everything the second round added.
This supersedes ticket 22 rather than replacing it: that collection is the foundation and
this one grows it.

**Blocked by:** 47, 48

**Owner:** Garfield

**Status:** done

- [x] Every request from ticket 22 still passes unchanged, or its change is deliberate and
      explained
- [x] New folders cover fleet, branches and one-way, money and quotations, delivery,
      maintenance, and the waitlist
- [x] Dates are still computed in pre-request scripts and never hardcoded
- [x] Identifiers created earlier in a run — a class, a branch, a claim — are captured into
      variables rather than pasted, so the collection runs end to end on a freshly seeded
      database
- [x] The negative cases are present explicitly: a full class, a one-way pair that is not
      enabled, a delivery address beyond the radius, a booking over a blackout, joining a
      waitlist for a class that is not full, and claiming after the window has expired
- [x] The FIFO chain is demonstrable: alpha cancels → beta gets offered → beta declines →
      gamma gets offered → gamma converts
- [x] The quotation is shown matching what the booking is then created with
- [x] The README documents the new commands, the new demo walkthrough, and every
      configurable value the new rules read
- [x] The collection runs green end to end against a freshly seeded database

## Notes

**Collection expanded from 9 folders (round 1) to 17 folders (both rounds).**
Name changed from "Rental Car Service — Round 1" to "Rental Car Service".

**New variables (20 added):**
`alpha_token`, `beta_token`, `gamma_token`, `branch_airport_id`, `vc_suv_id`,
`vc_classic_id`, `vehicle_suv_id`, `blackout_window_id`, `one_way_booking_id`,
`delivery_booking_id`, `waitlist_entry_beta_id`, `waitlist_entry_gamma_id`,
`waitlist_entry_fresh_id`, `claim_booking_id`, `alpha_booking_id`, `notification_id`,
`in_2`, `in_3`, `in_5`, `in_6`, `in_11`, `in_12`.

**Pre-request script** extended to compute `in_2`, `in_3`, `in_5`, `in_6`, `in_11`, `in_12`.

**00 — Setup** extended with 8 new discovery steps: Login Alpha/Beta/Gamma, Discover
Airport Branch, Discover SUV and Classic classes, Discover SUV vehicle, Discover Beta
and Gamma waitlist entries, Discover Alpha's SUV booking.

**New folders:**
- **09 — Availability**: free counts, Economy blackout reducing count from 3→2, SUV
  free_count=0 from alpha's booking, 422 reversed dates.
- **10 — Fleet (Admin)**: vehicle class and vehicle CRUD. Vehicle reads are admin-only
  (403 for registered user). Creates and cleans up a Demo Compact class.
- **11 — Branches, Distances & One-Way**: list branches (shows delivery radii), get
  individual branches, set/clear delivery radius, get branch distance, list one-way routes,
  one-way booking Siam→Airport (201), reverse direction Airport→Siam (409 not enabled).
- **12 — Quotations**: round-trip (rental line), one-way (+ relocation line), delivery
  (+ delivery line), all three combined, unpriced class Classic (409).
- **13 — Delivery Bookings**: create booking with delivery (201), beyond radius (409),
  branch with no delivery radius (409), missing delivery_distance_km (422), cleanup.
- **14 — Maintenance**: list (empty), create blackout on SUV vehicle, get window, verify
  free_count=0, booking refused (409 maintenance), overlap (409), user write (403), update,
  delete, verify availability restored.
- **15 — Waitlist & Claims**: full FIFO chain (see below), negative cases.
- **16 — Notifications**: list (newest first), mark read, idempotent re-read, 404 for
  another user's notification.

**FIFO chain (folder 15):**
1. Try to book full SUV → 409
2. Try to join Economy waitlist (not full) → 409
3. Fresh joins SUV waitlist → position 3
4. Fresh leaves waitlist
5. Beta at position 1, gamma at position 2 (confirmed)
6. Alpha cancels SUV booking → beta gets offered (same transaction)
7. Beta's state: "claimed"
8. Beta declines → gamma gets offered (lazy settle on next beta GET)
9. Gamma's state: "claimed"
10. Gamma converts → 201 booking; state → "converted"
11. Try to convert again → 409

**Expired claim** is not automated (requires waiting). The collection description explains:
set `CLAIM_WINDOW_MINUTES=1` in `.env`; after step 6, wait 1 minute before step 7.
Beta's state will read "expired" and gamma will be offered on the first read that settles.

**README updated:** credentials table now lists all 6 users (alpha/beta/gamma added);
Postman walkthrough updated to describe all 17 folders; smoke run count updated to 182;
configuration table adds CURRENCY, RELOCATION_RATE_PER_KM, DELIVERY_TIERS.
