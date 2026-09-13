"""The User model: a registered user, or an admin."""

import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class UserRole(str, enum.Enum):
    """Who someone is. Registered users book and review; admins manage.

    A user's role is never taken from a request body. Admins exist only because
    the seed command created them.
    """

    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    telephone: Mapped[str] = mapped_column(String(40), nullable=False)

    # Stored lowercased so that an address cannot be registered twice by
    # changing its case. The unique constraint is what actually enforces that.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)

    # A bcrypt digest. The plain password is never stored, logged, or returned.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", validate_strings=True),
        nullable=False,
        default=UserRole.user,
        server_default=UserRole.user.value,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
