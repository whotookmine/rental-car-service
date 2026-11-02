# Admin-recorded distances over geocoding

Branch distances — used to compute relocation fees on one-way rentals and to gate
one-way enablement — are recorded by an admin via a `PUT` route rather than derived
from branch addresses via an external mapping API.

The geocoding approach was considered and rejected on four grounds:

**API keys and quotas.** Every mapping service requires credentials. The project has
no secrets-management story for API keys, and a service that stops working when a
free-tier quota resets is not a service.

**Failure modes.** A geocoding call in the request path turns a third-party outage
into a 5xx for any route that needs a distance. Recording it once and at rest means
the routes that read it are as reliable as the database.

**Correctness.** Driving distance between two rental offices is not straight-line
distance, and map services disagree with each other and with the roads as actually
driven. An admin who manages those offices knows which figure appears on customer
receipts and can correct it; no algorithm does.

**Cost.** Pricing a relocation fee from a geocoded distance that differs from the
quoted amount by a rounding artefact would produce support requests and disputes.

## Consequences

- An admin must record the distance between two branches before a one-way route
  between them can be enabled. Attempting to enable without a recorded distance is
  refused with 409.
- A missing distance answers 404 rather than being assumed to be zero, because a zero
  relocation fee and an unknown one are different things.
- Distances are symmetric: one row covers both directions. Application code stores the
  pair in canonical form (smaller id first).
