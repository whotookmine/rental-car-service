"""The Branch model: a physical pickup location under a provider.

A provider used to be a single address. Branches split that address into one or
more specific locations a customer drives to. One-way rentals and delivery radii
are both defined between or around branches, so neither is expressible until a
branch exists as its own row.

A branch belongs to exactly one provider for its whole life. The provider is set
at creation from the path and the update shape carries no field for it, so there
is no request that could express a move.

A provider must always have at least one branch. The application layer enforces
this; it is not a database constraint, because the check is relative to a count
and not expressible as a simple FK rule.
"""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.providers.models import Provider


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)

    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    telephone: Mapped[str] = mapped_column(String(40), nullable=False)

    provider: Mapped[Provider] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Branch id={self.id} provider={self.provider_id} name={self.name!r}>"
        )
