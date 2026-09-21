"""The Review model: a rating and comment left by a booking's owner after the rental ends."""

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)

    # One review per booking; the unique constraint is the enforcement, not a
    # check-before-insert race. Deleting the booking cascades to this row.
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # 1–5 inclusive, validated on the schema before it reaches here.
    rating: Mapped[int] = mapped_column(Integer, nullable=False)

    comment: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Review id={self.id} booking={self.booking_id} rating={self.rating}>"
