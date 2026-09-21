"""Request and response shapes for reviews."""

from pydantic import BaseModel, ConfigDict, Field


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 1–5 inclusive, non-integer values rejected as 422.
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=1)


class ReviewUpdate(BaseModel):
    """New rating and comment for an existing review.

    Both fields are required: a review is one opinion with two parts, replaced
    wholesale. booking_id is absent and extra is forbidden, so an attempt to move
    a review to a different booking is refused loudly instead of silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=1)


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_id: int
    rating: int
    comment: str
