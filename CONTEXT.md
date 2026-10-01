# Rental Car Service

A web API through which registered users reserve cars from rental car providers for a
period of time, and afterwards rate the provider they rented from.

## Language

**Booking**:
A registered user's claim on one provider, for one vehicle class, for a rental period.
_Avoid_: Reservation, appointment, order, rental

**Rental Period**:
The span a booking covers, from its start date to its end date inclusive. A one-day
rental has a start date equal to its end date.
_Avoid_: Duration, date range, booking date

**Active Booking**:
A booking whose rental period has not yet ended. A registered user may hold at most
three active bookings; deleting a booking frees a slot immediately.
_Avoid_: Open booking, current booking, pending booking

**Provider**:
A business that rents out cars, which bookings are made against and users rate. Identified by
a name, address, and telephone number. Offers one or more vehicle classes.
_Avoid_: Rental car provider, shop, vendor, company, hospital

**Vehicle Class**:
A kind of car a provider rents out, such as economy, SUV or van — not an individual
car. Named and described, belonging to exactly one provider for its whole life. Its
capacity is the number of vehicles in it.
_Avoid_: Car type, category, model, vehicle group, tier

**Fully Booked**:
The state of a vehicle class on a given day when every one of its vehicles is held by a
booking covering that day. A class is fully booked for a rental period if it is fully
booked on any single day of it.
_Avoid_: Sold out, unavailable, no vacancies, booked out, occupied

**Vehicle**:
One individual car in a provider's fleet, identified by its plate and sitting in exactly
one of that provider's vehicle classes. A car may be reclassified within its provider's
catalogue but never passes to another provider.
_Avoid_: Unit, car, asset, fleet item, inventory item

**Blackout Window**:
A period, counted inclusively, during which one vehicle is off the road for servicing
and cannot be rented. Scheduled per vehicle, never per vehicle class: a workshop takes
one car in, not a category. Two windows on the same vehicle may not overlap, and a
window may be recorded for days that have already passed.
_Avoid_: Downtime, maintenance period, service slot, unavailability, outage

**Review**:
A rating from 1 to 5 with written comment that a registered user leaves against the
provider of one of their own bookings, once that booking's rental period has ended.
At most one review exists per booking.
_Avoid_: Rating, feedback, comment, testimonial

**Notification**:
A record the system writes to tell one registered user something, which that user reads
and may mark as read. Addressed to a person, never broadcast, and never created by a
request — only by a rule inside the system.
_Avoid_: Alert, message, email, push, inbox item

**Registered User**:
A person who has registered and may book, and who may review providers they have
booked. Never an admin.
_Avoid_: Customer, client, member, account

**Admin**:
A staff member who may view, edit, and delete any booking, and delete any review.
Admins do not hold bookings of their own and cannot be created through the API.
_Avoid_: Administrator, superuser, staff, moderator

**Retired Provider**:
A provider that no longer takes new bookings but whose record, existing bookings, and
reviews remain intact. Retiring is reversible and is the only form of provider removal.
_Avoid_: Deleted provider, inactive provider, disabled provider, archived provider
