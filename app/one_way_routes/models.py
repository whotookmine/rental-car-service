"""OneWayRoute: a directed pair of branches a provider allows one-way rentals between.

Enablement is directional: A→B and B→A are independent rows. No canonical ordering
is applied. If either branch is deleted the route is removed (CASCADE).
"""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.branches.models import Branch
from app.db.base_class import Base


class OneWayRoute(Base):
    __tablename__ = "one_way_routes"

    from_branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    to_branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"),
        primary_key=True,
    )

    from_branch: Mapped[Branch] = relationship(
        foreign_keys=[from_branch_id], lazy="joined"
    )
    to_branch: Mapped[Branch] = relationship(
        foreign_keys=[to_branch_id], lazy="joined"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OneWayRoute {self.from_branch_id}→{self.to_branch_id}>"
