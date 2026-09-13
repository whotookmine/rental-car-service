# 08 — Booking creation with date validation

**What to build:** A registered user reserves a car by booking a provider for a rental
period, giving a start and an end date. The system refuses rental periods that make no
sense. Start and end are plain dates with no time component, and every comparison against
today uses the business-timezone helper rather than the system clock.

**Blocked by:** 06

**Status:** ready-for-agent

- [ ] A registered user creates a booking against a provider for a start and end date
- [ ] The booking is created under the provider, which cannot be omitted
- [ ] The created booking records its owner from the token, never from the request body
- [ ] A rental period with the same start and end date is accepted as a one-day rental
- [ ] An end date before the start date is rejected as unprocessable
- [ ] A rental period longer than thirty days is rejected as unprocessable
- [ ] A start date in the past is rejected as unprocessable
- [ ] A start date of today is accepted
- [ ] Booking against a provider that does not exist reports not-found
- [ ] An unauthenticated caller is refused
- [ ] Dates are stored as dates with no time component, and "today" is computed in the
      configured business timezone
