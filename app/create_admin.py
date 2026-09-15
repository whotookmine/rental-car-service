"""Create an admin account.

Run with:
    uv run python -m app.create_admin
    uv run python -m app.create_admin --email admin@example.com --password secret123

Running twice with the same email is safe: the existing account is left untouched.
Admins cannot be created through the API; this command is the only path.
"""

import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.security import hash_password, validate_password
from app.db.session import engine

DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD = "admin1234"
DEFAULT_NAME = "Admin"
DEFAULT_TELEPHONE = "0000000000"


def create_admin(
    email: str,
    password: str,
    name: str,
    telephone: str,
) -> None:
    # The same rule registration applies. Without it the most privileged account
    # in the service could be given a weaker password than any ordinary user,
    # and an over-long one would reach bcrypt and raise.
    validate_password(password)

    with Session(engine) as db:
        existing = db.scalar(select(User).where(User.email == email.lower()))
        if existing is not None:
            print(
                f"Account {email!r} already exists "
                f"(role={existing.role.value}). No changes made."
            )
            return

        admin = User(
            name=name,
            telephone=telephone,
            email=email.lower(),
            password_hash=hash_password(password),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
        print(f"Admin created: {email!r}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create an admin account.")
    parser.add_argument("--email", default=DEFAULT_EMAIL, help="Admin email address")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Admin password (min 8 chars)")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Admin display name")
    parser.add_argument("--telephone", default=DEFAULT_TELEPHONE, help="Admin telephone number")
    args = parser.parse_args()

    try:
        create_admin(
            email=args.email,
            password=args.password,
            name=args.name,
            telephone=args.telephone,
        )
    except ValueError as exc:
        sys.exit(f"Refusing to create the admin: password {exc}")
