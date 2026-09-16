# Rental Car Service

A web API through which registered users reserve cars from rental car providers for a
period of time, and afterwards rate the provider they rented from.

## Language

**Booking**:
A reservation made by a registered user against one provider for a rental period.
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
a name, address, and telephone number. Individual vehicles are not modelled.
_Avoid_: Rental car provider, shop, vendor, company, hospital

**Review**:
A rating from 1 to 5 with written comment that a registered user leaves against the
provider of one of their own bookings, once that booking's rental period has ended.
At most one review exists per booking.
_Avoid_: Rating, feedback, comment, testimonial

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
