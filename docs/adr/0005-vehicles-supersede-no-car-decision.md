# Individual vehicles are now modelled (supersedes the no-Car decision)

The first round of work deliberately omitted a Car entity. A booking reserved a period with
a provider and nothing else; capacity was an integer on the vehicle class and was never
backed by rows. The reasoning at the time was sound: the brief mentioned no individual car,
and modelling one would have been building ahead of requirements.

The second round makes that untenable. Three requirements converge on the same need:

- **Maintenance blackout windows** (ticket 39) must be scheduled per car, not per class. A
  workshop takes one car in, not a category, and recording a window against a class would
  force every car in the class off the road for one car's service visit.
- **Capacity enforcement** (ticket 40) counts how many cars are on the road on any given day.
  Without rows for each car the count is the class's integer, which cannot be adjusted for
  cars in the workshop; those two numbers must meet in a single arithmetic expression or they
  will drift apart.
- **Plate-level administration**: an operator who manages a fleet needs to record which car
  is which, which provider it belongs to, and whether it has moved between classes. An
  integer count carries none of that.

A Vehicle entity — one row per car, foreign key to vehicle class, unique plate — satisfies
all three at once. The class's capacity becomes a derived count (`COUNT(vehicles)`) rather
than a stored integer, so it stays correct across adds and removes without a maintenance
path.

## Consequences

- Vehicle routes are admin-only. A plate is fleet administration; a renter books a kind of
  car and has no use for the individual car's identity.
- `vehicle_count` on a vehicle class is computed on read by aggregation, never stored.
- Every table that references a vehicle does so `ON DELETE RESTRICT`, so a car with a
  service history or a live booking cannot be silently deleted.
- The lock order is owner, then vehicle class, then vehicle — every path that takes more
  than one takes them in this order to prevent deadlocks.
