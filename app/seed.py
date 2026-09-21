"""Demo seed data.

Wipes all rows from bookings, providers, and users, then loads a fixed known
state so the whole feature set can be demonstrated from scratch.

Run with:
    uv run python -m app.seed

Re-running is safe: it always produces the same state.

Refuses to run when ENV=production.

Demo credentials
----------------
Admin:      admin@example.com   / admin1234
Demo user:  demo@example.com    / demo1234   (has an ended booking and an upcoming one)
Clean user: fresh@example.com   / fresh1234  (no bookings — walk through registration live)
"""

import sys
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.security import hash_password
from app.bookings.models import Booking
from app.core.clock import today
from app.core.config import get_settings
from app.db.session import engine
from app.providers.models import Provider


def _wipe(db: Session) -> None:
    # Delete in FK-safe order: bookings first (reviews will cascade once that
    # table exists), then providers and users.
    db.execute(text("DELETE FROM bookings"))
    db.execute(text("DELETE FROM providers"))
    db.execute(text("DELETE FROM users"))


def _users(db: Session) -> tuple[User, User, User]:
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
    db.add_all([admin, demo, fresh])
    db.flush()
    return admin, demo, fresh


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


def _bookings(db: Session, demo_user: User, providers: list[Provider]) -> None:
    t = today()
    active_provider = providers[0]

    # Ended booking: inserted directly through the ORM to bypass the no-past-dates
    # rule, which exists to protect users rather than to constrain fixtures.
    ended = Booking(
        user_id=demo_user.id,
        provider_id=active_provider.id,
        start_date=t - timedelta(days=20),
        end_date=t - timedelta(days=5),
    )

    # Upcoming booking: well within the 30-day maximum.
    upcoming = Booking(
        user_id=demo_user.id,
        provider_id=providers[1].id,
        start_date=t + timedelta(days=5),
        end_date=t + timedelta(days=15),
    )

    db.add_all([ended, upcoming])


def seed() -> None:
    settings = get_settings()
    if settings.env == "production":
        sys.exit("Refusing to wipe a production database.")

    with Session(engine) as db:
        _wipe(db)
        _, demo, _ = _users(db)
        providers = _providers(db)
        _bookings(db, demo, providers)
        db.commit()

    print("Seed complete.")
    print()
    print("  Admin:      admin@example.com  / admin1234")
    print("  Demo user:  demo@example.com   / demo1234   (ended + upcoming booking)")
    print("  Clean user: fresh@example.com  / fresh1234  (no bookings)")


if __name__ == "__main__":
    seed()
