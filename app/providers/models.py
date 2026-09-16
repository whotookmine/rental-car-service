"""The Provider model: a business that rents out cars, available for booking."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    telephone: Mapped[str] = mapped_column(String(40), nullable=False)

    # Retiring is the only form of removal. The row is never deleted.
    is_retired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Provider id={self.id} name={self.name!r} retired={self.is_retired}>"
