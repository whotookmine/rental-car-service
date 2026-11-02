"""Demo seed data.

Wipes every table it owns, then loads a fixed known state so the whole feature
set can be demonstrated from scratch.

Run with:
    uv run python -m app.seed

Re-running is safe: it always produces the same state.

Refuses to run when ENV=production.

Demo credentials
----------------
Admin:        admin@example.com   / admin1234
Demo user:    demo@example.com    / demo1234   (ended booking + upcoming booking, 2 notifications)
Fresh user:   fresh@example.com   / fresh1234  (no bookings — walk through registration live)
Alpha user:   alpha@example.com   / alpha1234  (holds the SUV booking that fills the class)
Beta user:    beta@example.com    / beta1234   (waitlist position 1 for SUV)
Gamma user:   gamma@example.com   / gamma1234  (waitlist position 2 for SUV)
"""

import sys
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.blackout_windows.models import BlackoutWindow
from app.bookings.models import Booking
from app.branch_distances.models import BranchDistance
from app.branches.models import Branch
from app.core.clock import now, today
from app.core.config import get_settings
from app.db.session import engine
from app.notifications.models import Notification, NotificationKind
from app.one_way_routes.models import OneWayRoute
from app.providers.models import Provider
from app.vehicle_classes.models import VehicleClass
from app.vehicles.models import Vehicle
from app.waitlist.models import WaitlistEntry


# Reverse dependency order. Bookings first, because they hold RESTRICT keys to
# both vehicle classes and branches and so block everything else. Routes and
# distances would cascade when their branches went, but deleting them explicitly
# keeps this list a readable statement of what the fixture owns.
#
# **Every new table that references one of these with RESTRICT has to be added
# here, above the table it points at.** Ticket 39's blackout windows were the
# third time this list went stale and broke the documented seed command -- after
# ticket 25's vehicle class and ticket 29's pickup branch -- and the first time it
# was caught before merging rather than by someone trying to demo.
_WIPE_ORDER = (
    "notifications",
    "waitlist_entries",
    "blackout_windows",
    "bookings",
    "vehicles",
    "vehicle_classes",
    "one_way_routes",
    "branch_distances",
    "branches",
    "providers",
    "users",
)


def _wipe(db: Session) -> None:
    """Empty every table the fixture owns, children before parents.

    Reviews are not listed: they cascade with the bookings they belong to.
    """
    for table in _WIPE_ORDER:
        db.execute(text(f"DELETE FROM {table}"))


def _users(db: Session) -> tuple[User, User, User, User, User, User]:
    admin = User(
        name="Admin",
        telephone="0000000000",
        email="admin@example.com",
        password_hash=hash_password("admin1234"),
        role=UserRole.admin,
    )
    demo = User(
        name="Demo User",
        telephone="0811111111",
        email="demo@example.com",
        password_hash=hash_password("demo1234"),
        role=UserRole.user,
    )
    fresh = User(
        name="Fresh User",
        telephone="0822222222",
        email="fresh@example.com",
        password_hash=hash_password("fresh1234"),
        role=UserRole.user,
    )
    # Alpha holds the booking that fills the SUV class for the demo range,
    # so a waitlist can be joined immediately without first booking it out by hand.
    alpha = User(
        name="Alpha User",
        telephone="0833333333",
        email="alpha@example.com",
        password_hash=hash_password("alpha1234"),
        role=UserRole.user,
    )
    # Beta and gamma are in the waitlist queue (beta first, gamma second),
    # so FIFO order is visible without manually joining mid-demo.
    beta = User(
        name="Beta User",
        telephone="0844444444",
        email="beta@example.com",
        password_hash=hash_password("beta1234"),
        role=UserRole.user,
    )
    gamma = User(
        name="Gamma User",
        telephone="0855555555",
        email="gamma@example.com",
        password_hash=hash_password("gamma1234"),
        role=UserRole.user,
    )
    db.add_all([admin, demo, fresh, alpha, beta, gamma])
    db.flush()
    return admin, demo, fresh, alpha, beta, gamma


def _providers(db: Session) -> list[Provider]:
    providers = [
        Provider(name="Fast Wheels", address="12 Sukhumvit Rd, Bangkok", telephone="021111111"),
        Provider(name="City Rentals", address="88 Silom Rd, Bangkok", telephone="022222222"),
        Provider(name="Budget Drive", address="45 Rama IV Rd, Bangkok", telephone="023333333"),
        Provider(name="Old Timer Cars", address="7 Charoen Krung Rd, Bangkok", telephone="024444444", is_retired=True),
    ]
    db.add_all(providers)
    db.flush()
    return providers


def _branches(db: Session, providers: list[Provider]) -> list[Branch]:
    """Pickup locations. Every provider needs at least one; the first gets two.

    A booking must name a pickup branch, so no provider can be bookable without
    one. The first provider gets a second branch because a one-way rental needs
    two, and the whole one-way feature is undemonstrable otherwise.

    Siam has a delivery radius; Don Mueang Airport does not. This gives one branch
    of each kind so the delivery refusal ("branch does not offer delivery") can be
    demonstrated as well as the happy path.
    """
    branches = [
        Branch(
            provider_id=providers[0].id,
            name="Siam",
            address="991 Rama I Rd, Bangkok",
            telephone="021111101",
            delivery_radius_km=20,
        ),
        Branch(
            provider_id=providers[0].id,
            name="Don Mueang Airport",
            address="222 Vibhavadi Rangsit Rd, Bangkok",
            telephone="021111102",
        ),
        Branch(
            provider_id=providers[1].id,
            name="Silom",
            address="88 Silom Rd, Bangkok",
            telephone="022222201",
        ),
        Branch(
            provider_id=providers[2].id,
            name="Rama IV",
            address="45 Rama IV Rd, Bangkok",
            telephone="023333301",
        ),
        Branch(
            provider_id=providers[3].id,
            name="Charoen Krung",
            address="7 Charoen Krung Rd, Bangkok",
            telephone="024444401",
        ),
    ]
    db.add_all(branches)
    db.flush()
    return branches


def _one_way_service(db: Session, branches: list[Branch]) -> None:
    """A distance and a one-way enablement for the first provider's two branches.

    Enabled in **one direction only**, Siam to the airport. That is deliberate:
    the directional refusal is the easiest rule in the one-way feature to get
    wrong, and a fixture that enables both ways would hide it. Attempting the
    reverse is a conflict, which a demo can show in one request.

    The distance has to exist first -- enabling a pair with no recorded distance
    is refused, since the relocation fee could not be computed.
    """
    siam, airport = branches[0], branches[1]

    # Canonical ordering: the smaller branch id is always stored first, which is
    # how the model keeps one row covering a symmetric distance.
    low, high = sorted((siam.id, airport.id))
    db.add(BranchDistance(from_branch_id=low, to_branch_id=high, distance_km=27.5))
    db.add(OneWayRoute(from_branch_id=siam.id, to_branch_id=airport.id))
    db.flush()


def _vehicle_classes(db: Session, providers: list[Provider]) -> list[VehicleClass]:
    """One kind of car per provider, plus a second for the first.

    A booking has to name a class, so the fixture needs somewhere for its
    bookings to point. Two under the first provider so that a demo has something
    to choose between.

    Daily rates are set on all but one. "Classic" is left unpriced on purpose, so
    that a demo can show a quotation refusing to price a class rather than
    quietly quoting zero.
    """
    classes = [
        VehicleClass(
            provider_id=providers[0].id,
            name="Economy",
            description="Small, cheap, four seats.",
            daily_rate=Decimal("1200.00"),
        ),
        VehicleClass(
            provider_id=providers[0].id,
            name="SUV",
            description="Seven seats and room for luggage.",
            daily_rate=Decimal("2500.00"),
        ),
        VehicleClass(
            provider_id=providers[1].id,
            name="Economy",
            description="Small, cheap, four seats.",
            daily_rate=Decimal("1100.50"),
        ),
        VehicleClass(
            provider_id=providers[2].id,
            name="Van",
            description="Twelve seats for a group.",
            daily_rate=Decimal("3400.00"),
        ),
        VehicleClass(
            provider_id=providers[3].id,
            name="Classic",
            description="Older cars, kept on the books after retirement.",
        ),
    ]
    db.add_all(classes)
    db.flush()
    return classes


def _vehicles(db: Session, classes: list[VehicleClass]) -> list[Vehicle]:
    """Cars for each class, because capacity is now enforced.

    Without these every seeded class would have capacity zero and refuse every
    booking, including the fixture's own. Counts differ on purpose: the demo
    should be able to fill a small class and see the refusal without creating
    three bookings first, while a larger one stays bookable.

    Vehicle order is stable across re-seeds within a single database lifecycle:
    Economy(FW)[0..2], SUV(FW)[3], Economy(CR)[4..6], Van[7..8], Classic[9].
    _blackout_windows uses index 0 (first Economy vehicle).
    """
    counts = {
        "Economy": 3,
        "SUV": 1,
        "Van": 2,
        "Classic": 1,
    }
    vehicles = []
    plate_number = 1000
    for vehicle_class in classes:
        for _ in range(counts[vehicle_class.name]):
            plate_number += 1
            vehicles.append(
                Vehicle(vehicle_class_id=vehicle_class.id, plate=f"1กข{plate_number}")
            )
    db.add_all(vehicles)
    db.flush()
    return vehicles


def _bookings(
    db: Session,
    demo_user: User,
    alpha_user: User,
    providers: list[Provider],
    classes: list[VehicleClass],
    branches: list[Branch],
) -> tuple[Booking, Booking, Booking]:
    t = today()

    # Ended booking: inserted directly through the ORM to bypass the no-past-dates
    # rule, which exists to protect users rather than to constrain fixtures.
    #
    # Made one-way, Siam to the airport, which is the direction enabled above.
    # It gives the fixture one booking of each shape, and it is the ended one
    # deliberately: the demo review has to attach to a finished rental, and a
    # one-way rental is the more interesting thing to have a review of.
    ended = Booking(
        user_id=demo_user.id,
        provider_id=providers[0].id,
        vehicle_class_id=classes[0].id,
        pickup_branch_id=branches[0].id,
        dropoff_branch_id=branches[1].id,
        start_date=t - timedelta(days=20),
        end_date=t - timedelta(days=5),
    )

    # Upcoming booking: well within the 30-day maximum, and a round trip --
    # no drop-off branch, which is the ordinary case and must stay the simplest.
    upcoming = Booking(
        user_id=demo_user.id,
        provider_id=providers[1].id,
        vehicle_class_id=classes[2].id,
        pickup_branch_id=branches[2].id,
        start_date=t + timedelta(days=5),
        end_date=t + timedelta(days=15),
    )

    # Alpha fills the SUV class (1 vehicle) for a known future range, so the
    # waitlist can be joined immediately without first booking it out by hand.
    # Inserted through the ORM like the ended booking above.
    suv_full = Booking(
        user_id=alpha_user.id,
        provider_id=providers[0].id,
        vehicle_class_id=classes[1].id,   # SUV
        pickup_branch_id=branches[0].id,   # Siam
        start_date=t + timedelta(days=3),
        end_date=t + timedelta(days=10),
    )

    db.add_all([ended, upcoming, suv_full])
    return ended, upcoming, suv_full


def _notifications(
    db: Session,
    demo_user: User,
    providers: list[Provider],
    ended: Booking,
    upcoming: Booking,
) -> None:
    """A couple of notifications for the demo user.

    **Nothing in the service emits a notification yet.** The waitlist is the first
    producer (tickets 43 to 46), so without these rows `GET /notifications` could
    only ever be demonstrated returning an empty list, and marking one read could
    not be demonstrated at all.

    Both describe something that is **actually true of this fixture** rather than
    an invented event: the demo user really does hold an ended booking that is
    waiting to be reviewed, and really does hold one starting soon. A fixture that
    asserts a fact the rest of the fixture contradicts is worse than no fixture.

    One read and one unread, because "newest first" and "has it been read" are both
    only visible when the rows differ.
    """
    db.add_all(
        [
            # Older, and already read.
            Notification(
                user_id=demo_user.id,
                kind=NotificationKind.booking_confirmed,
                message=(
                    f"Your booking with {providers[1].name} starts on "
                    f"{upcoming.start_date}."
                ),
                created_at=now() - timedelta(days=4),
                read_at=now() - timedelta(days=3),
            ),
            # Newer, and unread, so it sorts first and a demo has something to mark.
            Notification(
                user_id=demo_user.id,
                kind=NotificationKind.booking_ended,
                message=(
                    f"Your rental with {providers[0].name} ended on "
                    f"{ended.end_date}. You can now leave a review."
                ),
                created_at=now() - timedelta(days=1),
            ),
        ]
    )


def _blackout_windows(db: Session, vehicles: list[Vehicle]) -> None:
    """One Economy vehicle in the workshop for a known future range.

    The Economy class has 3 cars, so effective capacity during this window is 2.
    Availability for that range will show free_count: 2 instead of 3.

    Vehicle: vehicles[0], the first Fast Wheels Economy car.
    """
    t = today()
    db.add(
        BlackoutWindow(
            vehicle_id=vehicles[0].id,
            start_date=t + timedelta(days=2),
            end_date=t + timedelta(days=6),
        )
    )
    db.flush()


def _waitlist_entries(
    db: Session,
    beta: User,
    gamma: User,
    providers: list[Provider],
    classes: list[VehicleClass],
    suv_full: Booking,
) -> None:
    """Beta and gamma queue for the SUV class on the same range as alpha's booking.

    Beta joined earlier (position 1); gamma joined later (position 2). The
    two-minute gap is enough to show FIFO ordering without making the timestamps
    look contrived.
    """
    db.add_all(
        [
            WaitlistEntry(
                user_id=beta.id,
                provider_id=providers[0].id,
                vehicle_class_id=classes[1].id,
                start_date=suv_full.start_date,
                end_date=suv_full.end_date,
                created_at=now() - timedelta(minutes=10),
            ),
            WaitlistEntry(
                user_id=gamma.id,
                provider_id=providers[0].id,
                vehicle_class_id=classes[1].id,
                start_date=suv_full.start_date,
                end_date=suv_full.end_date,
                created_at=now() - timedelta(minutes=5),
            ),
        ]
    )
    db.flush()


def seed() -> None:
    settings = get_settings()
    if settings.env == "production":
        sys.exit("Refusing to wipe a production database.")

    with Session(engine) as db:
        _wipe(db)
        _, demo, _, alpha, beta, gamma = _users(db)
        providers = _providers(db)
        branches = _branches(db, providers)
        _one_way_service(db, branches)
        classes = _vehicle_classes(db, providers)
        vehicles = _vehicles(db, classes)
        ended, upcoming, suv_full = _bookings(db, demo, alpha, providers, classes, branches)
        # Flushed so the bookings have the dates the notifications quote; they are
        # already set, but flushing keeps the dependency explicit rather than
        # relying on attribute order.
        db.flush()
        _notifications(db, demo, providers, ended, upcoming)
        _blackout_windows(db, vehicles)
        _waitlist_entries(db, beta, gamma, providers, classes, suv_full)
        db.commit()

    t = today()
    suv_start = t + timedelta(days=3)
    suv_end = t + timedelta(days=10)
    bw_start = t + timedelta(days=2)
    bw_end = t + timedelta(days=6)

    print("Seed complete.")
    print()
    print("  Admin:        admin@example.com   / admin1234")
    print("  Demo user:    demo@example.com    / demo1234   (ended + upcoming booking, 2 notifications)")
    print("  Fresh user:   fresh@example.com   / fresh1234  (no bookings)")
    print("  Alpha user:   alpha@example.com   / alpha1234  (holds SUV booking that fills the class)")
    print("  Beta user:    beta@example.com    / beta1234   (waitlist position 1 for Fast Wheels SUV)")
    print("  Gamma user:   gamma@example.com   / gamma1234  (waitlist position 2 for Fast Wheels SUV)")
    print()
    print(f"  Fast Wheels — Siam branch: delivery available, radius 20 km")
    print(f"  Fast Wheels — SUV class: FULL for {suv_start} to {suv_end} (alpha's booking fills 1/1 cars)")
    print(f"  Fast Wheels — Economy: one car blacked out {bw_start} to {bw_end} (effective capacity: 2/3)")
    print(f"  Waitlist: beta (position 1) and gamma (position 2) queued for SUV on {suv_start} to {suv_end}")


if __name__ == "__main__":
    seed()
