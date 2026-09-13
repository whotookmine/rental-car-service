# Rental Car Service — Backend API

Status: ready-for-agent

Terminology follows [CONTEXT.md](../../CONTEXT.md). Decisions with lasting consequences
are recorded in [docs/adr](../../docs/adr) and are binding on this spec. The agreed
ruleset lives in [docs/SPEC.md](../../docs/SPEC.md); this document restates it in
problem-and-story form and does not contradict it.

## Problem Statement

Someone who wants to rent a car has no way to hold a slot with a rental company ahead of
time. They cannot see which companies are available, cannot tell a good one from a bad
one before committing, and once they have arranged something there is no record of it
they can check, change, or cancel. Rental companies are equally unserved: nothing tracks
who has booked what, and a company that stops trading cannot be taken out of circulation
without destroying the history of everyone who ever rented from it.

Staff running the service have no way to intervene. When a customer's booking is wrong,
or a review is abusive, there is no mechanism to correct it.

## Solution

A REST API where a person registers, logs in, browses rental car providers with their
average ratings, and holds up to three active bookings at a time. Each booking names one
provider and a rental period. Bookings can be viewed, re-dated, and deleted by the person
who made them. Once a booking's rental period has ended, its owner may rate the provider
from 1 to 5 with a written review, and those ratings roll up into the average shown
against each provider in the list — so the next customer chooses better than the last.

Admins see and act on every booking, and can remove reviews that should not stand. Admins
manage the provider catalogue, retiring providers that have stopped trading without
disturbing the bookings and reviews that reference them.

There is no frontend. The API is exercised through Postman.

## User Stories

### Registration and authentication

1. As a visitor, I want to register with my name, telephone number, email, and password, so that I can become a registered user and start booking.
2. As a visitor, I want my registration to be rejected if the email is already in use, so that two people cannot end up sharing an identity.
3. As a visitor, I want my email to be treated case-insensitively, so that I am not locked out by typing it differently than I registered it.
4. As a visitor, I want a password of fewer than eight characters to be rejected, so that my account is not trivially guessable.
5. As a visitor, I want to receive a token the moment I register, so that I can start using the system without a separate login step.
6. As a registered user, I want to log in with my email and password, so that I can use the system on a new device or after my token expires.
7. As a registered user, I want a wrong password to be refused without telling me whether the email exists, so that my account cannot be discovered by probing.
8. As a registered user, I want to log out, so that I can end my session on the machine I am using.
9. As a registered user, I want my password never to appear in any response, so that it cannot leak through the API.
10. As a registered user, I want my token to stop working after an hour, so that a token left behind on a shared machine has a bounded life.
11. As a registered user, I want requests without a valid token to be refused, so that nobody can act as me.
12. As a visitor, I want to be unable to make myself an admin during registration, so that the system's privileged powers are not self-service.

### Browsing providers

13. As a registered user, I want to see the list of providers, so that I can choose who to rent from.
14. As a registered user, I want each provider in the list to show its name, address, and telephone number, so that I can judge whether it is convenient for me.
15. As a registered user, I want each provider in the list to show its average rating and review count, so that I can tell a well-regarded provider from an untested one.
16. As a registered user, I want a provider with no reviews to show no rating rather than a zero, so that an untested provider is not mistaken for a terrible one.
17. As a registered user, I want retired providers left out of the list, so that I am not offered companies that are no longer trading.
18. As a registered user, I want to fetch a provider directly by its identifier even if it is retired, so that I can still see who I booked with after they stop trading.

### Making bookings

19. As a registered user, I want to book a provider for a rental period by giving a start and end date, so that I have a car reserved for my trip.
20. As a registered user, I want to book for a single day by giving the same start and end date, so that short rentals are possible.
21. As a registered user, I want a booking whose end date falls before its start date to be rejected, so that I cannot create a nonsensical rental.
22. As a registered user, I want a rental period longer than thirty days to be rejected, so that I cannot accidentally tie up a booking slot indefinitely.
23. As a registered user, I want a booking that starts in the past to be rejected, so that I cannot create a reservation for a date that has already gone.
24. As a registered user, I want to be refused when I try to hold a fourth active booking, with a message that tells me why, so that I understand the limit rather than guessing.
25. As a registered user, I want bookings whose rental periods have ended to stop counting against my limit, so that past rentals do not permanently consume my allowance.
26. As a registered user, I want to hold bookings whose rental periods overlap, so that I can arrange rentals for more than one person or more than one trip at a time.
27. As a registered user, I want to be refused when I try to book a retired provider, so that I do not reserve with a company that has stopped trading.
28. As a registered user, I want to be refused when I book against a provider that does not exist, so that a typo does not create a dangling reservation.

### Managing bookings

29. As a registered user, I want to view all of my bookings, so that I can see what I have reserved.
30. As a registered user, I want to view a single booking of mine in detail, so that I can check its dates and provider.
31. As a registered user, I want to see which provider each of my bookings is with, so that I know who to contact.
32. As a registered user, I want to change the dates of one of my bookings, so that I can adjust my plans without cancelling.
33. As a registered user, I want date changes validated the same way as when I created the booking, so that I cannot edit my way into an invalid rental.
34. As a registered user, I want to be able to extend a booking that is already underway, so that I can keep the car longer.
35. As a registered user, I want to be unable to change which provider a booking is with, so that a booking always reflects the company I actually reserved with.
36. As a registered user, I want to delete a booking I no longer need, so that I can cancel a trip.
37. As a registered user, I want deleting a booking to free up a slot immediately, so that I can rebook straight away.
38. As a registered user, I want another user's booking to appear not to exist when I try to view, edit, or delete it, so that nobody can discover how much other people are renting by guessing identifiers.

### Reviewing

39. As a registered user, I want to rate a provider from 1 to 5 and write a review after my rental period has ended, so that I can share what the experience was actually like.
40. As a registered user, I want to be refused when I try to review a booking whose rental period has not ended, so that reviews only ever describe finished rentals.
41. As a registered user, I want to be refused when I try to review the same booking twice, so that one rental carries one opinion.
42. As a registered user, I want to be able to review the same provider again after a separate rental, so that a changed experience can be recorded.
43. As a registered user, I want to be refused when I try to review someone else's booking, so that ratings come only from people who actually rented.
44. As a registered user, I want a rating outside the range 1 to 5 to be rejected, so that the average stays meaningful.
45. As a registered user, I want to edit the rating and comment on a review I wrote, so that I can correct a mistake or change my mind.
46. As a registered user, I want to delete a review I wrote, so that I can withdraw an opinion without deleting the booking it belongs to.
47. As a registered user, I want to be unable to move a review to a different booking, so that every review stays attached to the rental it describes.
48. As a registered user, I want deleting a booking to take its review with it, so that no review survives without the rental that justified it.
49. As a registered user, I want to be able to review a provider that has since retired, so that my experience is still recorded.
50. As a registered user, I want a booking that already carries a review to be un-extendable past the point where its rental period is no longer ended, so that a review never describes a rental still in progress.

### Admin — bookings

51. As an admin, I want to view every booking in the system, so that I can support customers and see what is happening.
52. As an admin, I want to view any single booking in detail, so that I can investigate a specific complaint.
53. As an admin, I want to change the dates on any booking, so that I can correct a customer's mistake on their behalf.
54. As an admin, I want to delete any booking, so that I can remove one that should not stand.
55. As an admin, I want my edits validated by exactly the same rules that apply to the booking's owner, so that I cannot accidentally create data the system considers impossible.
56. As an admin, I want to be unable to change which provider a booking is with, so that the historical record of who was booked stays honest.
57. As an admin, I want not to hold bookings of my own, so that my role is unambiguously to manage rather than to rent.

### Admin — reviews

58. As an admin, I want to delete an inappropriate review, so that abusive content does not stay visible against a provider.
59. As an admin, I want deleting a review to leave its booking intact, so that removing bad content does not destroy a customer's rental record.
60. As an admin, I want a booking whose review I deleted to become reviewable again, so that the customer can write a proper one.
61. As an admin, I want a provider's average rating to update when I remove a review, so that the displayed rating reflects only reviews that still stand.

### Admin — providers

62. As an admin, I want to add a provider with its name, address, and telephone number, so that the catalogue reflects the companies we work with.
63. As an admin, I want to edit a provider's details, so that I can correct an address or a phone number.
64. As an admin, I want to retire a provider that has stopped trading, so that nobody books with it any more.
65. As an admin, I want retiring a provider to leave its existing bookings and reviews untouched, so that customer history survives a catalogue change.
66. As an admin, I want to bring a retired provider back, so that a mistaken retirement or a returning company can be handled.
67. As an admin, I want to see retired providers when I ask for them explicitly, so that I can manage the full catalogue rather than only the bookable part.
68. As a registered user, I want to be unable to create, edit, or retire providers, so that the catalogue is not open to tampering.

### Operating the system

69. As a developer, I want one command to load demo data, so that I can show the system working from a clean database.
70. As a developer, I want the seed data to include a booking whose rental period has already ended, so that the review feature can be demonstrated despite past-dated bookings being un-creatable through the API.
71. As a developer, I want the seed data to include a retired provider, so that retirement is visible in a demo.
72. As a developer, I want the seed to leave the ended booking unreviewed, so that the demo performs the first review live.
73. As a developer, I want re-running the seed to produce the same clean state rather than duplicates, so that a demo can be repeated.
74. As a developer, I want the seed to refuse to run against production, so that demo fixtures cannot destroy real data.
75. As a developer, I want the database schema to be reproducible from empty by running migrations, so that anyone can stand the system up.
76. As a developer, I want to import the API's OpenAPI document into Postman, so that I have a working collection without building every request by hand.
77. As a developer, I want no secret to be committed to the repository, so that the signing key cannot leak.
78. As a developer, I want every response to arrive within three seconds, so that the performance requirement is met.

## Implementation Decisions

### Stack and structure

- Python with FastAPI, SQLAlchemy 2.0, Alembic for migrations, Pydantic for request and
  response schemas, and PostgreSQL. PostgreSQL was chosen over the MongoDB Atlas option
  the brief also permits; see ADR 0001.
- Feature-first module layout, one module per area — authentication, bookings, providers,
  reviews — each owning its model, schemas, routing, and rules. A single module imports
  every model so that migration autogeneration sees all tables.
- Request and response bodies are snake_case bare resources, with FastAPI's default error
  shape. No success/data envelope. Error messages are specific enough to explain
  themselves without a separate error code vocabulary.

### Domain model

- There is no Car. A Booking reserves a Rental Period with one Provider. The brief's
  reference to "cars" is a unit of counting, not an entity, and reviews target providers.
- **User** carries name, telephone, email, password hash, and a role of either user or
  admin. The role defaults to user and is not settable through any endpoint; admins are
  created only by the seed script.
- **Provider** carries name, address, telephone, and a retirement flag.
- **Booking** carries its owner, its provider, a start date, and an end date.
- **Review** carries its booking, a rating from 1 to 5, and a comment. A uniqueness
  constraint on the booking enforces one review per booking.
- Booking state is derived, never stored. There is no status field: an Active Booking is
  one whose rental period has not ended, and a reviewable booking is one whose rental
  period has. Deletion is a real deletion, not a flag.

### Dates and time

- Start and end dates are date values with no time component.
- "Today" is computed in a configured business timezone rather than UTC, through a single
  shared helper that every rule uses. No rule computes the current date directly. Without
  this, the seven-hour offset means that between midnight and 07:00 local a booking that
  ended yesterday is not yet reviewable and a booking starting today is rejected as
  past-dated.

### Booking rules

- End date must be on or after start date; rental period at most thirty days.
- Start date must not be in the past **on creation**. Updates may touch past dates, so
  that a booking already underway can be extended and an admin can correct history.
- At most three Active Bookings per registered user. Deleting a booking frees a slot
  immediately.
- Overlapping bookings by the same user are permitted. With no vehicle inventory they
  contradict nothing, and the active cap already bounds abuse.
- Only the dates are mutable. The provider is fixed at creation, which keeps every review
  attached to the company actually rented from.
- Admin edits run through the same code path and the same validation as owner edits,
  including the three-booking cap measured against the booking's owner. Admins have wider
  scope, not weaker rules.
- A booking carrying a review cannot be edited such that its rental period would no longer
  be ended.

### Review rules

- A review is created against a booking the requester owns, whose rental period has ended.
- Rating and comment are mutable by the review's author; the booking is not.
- Deleting a booking cascades to its review at the database level, which is one of the
  reasons PostgreSQL was chosen. Deleting a review leaves the booking intact and
  reviewable again.
- A known and accepted consequence: a user can erase their own unfavourable review by
  deleting the booking. The brief carries no anti-abuse requirement, so this is allowed.

### Provider rules

- Average rating and review count are computed on read by aggregating over reviews. They
  are never stored. Denormalised counters would drift silently, because the
  booking-to-review cascade fires in the database and would bypass any application-level
  counter update.
- A provider with no reviews reports no average rather than zero. Averages are rounded to
  one decimal place in responses and held at full precision in storage.
- Providers are retired, never deleted; see ADR 0004. Retirement stops new bookings and
  removes the provider from the bookable list, while leaving its bookings and reviews
  intact and its record fetchable by identifier. Retirement is reversible.
- The delete verb on a provider performs retirement. This is a deliberate deviation from
  strict REST semantics, kept because it is the verb an admin and a test will reach for.

### Authorization and API surface

- Users and admins share the same routes. Scope widens by role: a request for bookings
  returns the requester's own bookings, or all bookings when the requester is an admin.
- Bookings are created under their provider, since a booking cannot exist without one.
  Reading, updating, and deleting a booking address it directly by identifier.
- Acting on a booking the requester does not own reports not-found rather than forbidden,
  so that booking identifiers cannot be enumerated to measure other users' activity. The
  accepted cost is that a permissions bug and a genuinely missing record are
  indistinguishable from outside.
- Provider creation, editing, and retirement are admin-only. Reading providers is open to
  any authenticated user.

### Authentication

- Stateless JWT valid for sixty minutes, configurable by environment variable, with no
  refresh token. Logout is client-side: the endpoint exists to satisfy the requirement but
  invalidates nothing server-side. See ADR 0003. The sixty-minute expiry is the entire
  mitigation behind the confidentiality requirement, so it should not be raised.
- Passwords are hashed with bcrypt. Minimum length eight, no complexity rules.
- Registration returns a token directly, so that registration and login are one step.

### Status codes

- Conflict for state that is wrong although the request is well-formed: a fourth active
  booking, booking a retired provider, reviewing a booking that has not ended, reviewing
  the same booking twice.
- Unprocessable for malformed input: date ordering, rental length, rating range.
- Not-found for acting on another user's booking.

### Configuration

- Secrets live in an untracked environment file with a tracked example alongside. The
  signing key is never hardcoded.
- Migrations are committed, so the schema is reproducible from an empty database.

## Testing Decisions

There is **no automated test suite**. Verification is manual, through a committed Postman
collection, which is what the usability requirement asks for. This is a deliberate choice
and its cost is recorded below rather than hidden.

- A good check here exercises **external behaviour only** — a request in, a status code
  and body out. No check should depend on module structure, function names, or storage
  layout, so that the implementation can be reorganised without invalidating the
  collection.
- The collection is organised to mirror the user stories: an authentication folder, a
  provider-browsing folder, a booking lifecycle folder, a review folder, and an admin
  folder. Each request carries assertions on status code and on the fields that
  distinguish success from the failure modes above.
- **Dates are computed in pre-request scripts relative to the current date, never
  hardcoded.** A collection with literal dates passes today and fails silently in three
  months, because every date rule in this system is relative to now.
- The token is captured from the login response into a collection variable and reused, so
  that the collection runs end to end without manual copying.
- The negative cases matter more than the positive ones and must be present explicitly:
  the fourth active booking, the reversed date range, the thirty-one-day rental, the
  past-dated creation, the review before the rental period ends, the second review on one
  booking, the booking against a retired provider, and one user reaching for another
  user's booking.
- Two rules cannot be verified honestly through the collection alone, because they depend
  on the passage of time and on data the API refuses to create: that an ended booking
  stops counting toward the three-booking cap, and that an ended booking becomes
  reviewable. Both are demonstrated using the seeded ended booking. Neither is regression
  -protected; a change that breaks them will not be caught automatically.
- The seed script is the fixture mechanism. It writes the ended booking through the ORM,
  deliberately bypassing the API-level rule against past-dated creation, because that rule
  exists to protect users rather than to constrain fixtures.

There is no prior art in this repository — no code exists yet, so the collection is the
first testing artefact.

## Out of Scope

- **Any frontend.** Excluded by the project constraints.
- **Cars, vehicle models, and inventory.** The brief models providers, not fleets. A
  future requirement introducing cars would be an additive change: a booking gains an
  optional vehicle reference.
- **Payment, pricing, and deposits.** Not mentioned anywhere in the brief.
- **Booking approval or confirmation by the provider.** There is no workflow; a booking
  exists the moment it is created.
- **Cancellation as a distinct concept.** The brief says delete, and deletion is literal.
- **Automated tests.** Decided against; see Testing Decisions.
- **Token revocation and refresh tokens.** See ADR 0003.
- **Pagination, sorting, and filtering** on the provider and booking lists.
- **Editing a user's own profile**, changing a password, and password reset.
- **Rate limiting, account lockout, and email verification.**
- **Recording who a rental is actually for** when a user books on someone else's behalf.
  Overlapping bookings are permitted, but the second person is not modelled; doing so
  would raise questions about whether the booking cap applies per account or per renter
  that the brief does not answer.
- **Soft deletion of bookings and reviews.** Only providers are soft-deleted.
- **Deployment, hosting, and CI.**

## Further Notes

- This brief is a re-skin of a common appointment-booking exercise. Vocabulary from that
  lineage — appointments, hospitals — must not leak into schema, routes, or responses;
  the glossary lists the terms to avoid.
- The brief itself is internally inconsistent: the core requirement describes a booking
  as having a single date, while the first additional requirement refers to a booking's
  rental period ending. This spec resolves that in favour of a period, with a one-day
  rental expressed as equal start and end dates, so that the original wording remains
  satisfiable.
- The brief never says who creates providers. This spec gives admins a provider catalogue
  and seeds an initial set, on the grounds that an admin with sweeping power over bookings
  but no control over what those bookings point at is a strange figure.
- The brief never grants a user the power to edit or delete their own review, although it
  grants full booking CRUD. This spec grants it, because the booking-to-review cascade
  already gives users a destructive route to the same outcome; offering the direct route
  is better for the data than forcing them through booking deletion.
- Further additional requirements are expected. The derived-state model — no status field,
  everything computed from dates — is the part most likely to need revisiting if a future
  requirement introduces approval, cancellation, or payment.
