"""The BranchDistance model: the distance in km between two branches.

Distances are typed in by an admin rather than computed from coordinates.
An external geocoding API would mean keys, quotas, network failures and cost
for a number an admin can type once.

Symmetry is enforced by canonical ordering: the branch with the smaller id is
always stored as `from_branch_id`. Application code normalises the pair before
every read and write, so a single row covers both directions and the composite
primary key prevents duplicates.

If either branch is deleted, its distances are removed with it (CASCADE). A
distance between non-existent branches is meaningless, and cascade avoids
leaving orphan rows that would silently answer zero for deleted branches.
"""

from sqlalchemy import Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.branches.models import Branch
from app.db.base_class import Base


class BranchDistance(Base):
    __tablename__ = "branch_distances"

    # Canonical: from_branch_id < to_branch_id always. The pair is the natural
    # key; a surrogate integer PK would add nothing while hiding the constraint.
    from_branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"),
        primary_key=True,
    )
    to_branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"),
        primary_key=True,
    )

    distance_km: Mapped[float] = mapped_column(Float, nullable=False)

    from_branch: Mapped[Branch] = relationship(
        foreign_keys=[from_branch_id], lazy="joined"
    )
    to_branch: Mapped[Branch] = relationship(
        foreign_keys=[to_branch_id], lazy="joined"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<BranchDistance {self.from_branch_id}↔{self.to_branch_id} "
            f"{self.distance_km}km>"
        )
