"""Request and response shapes for branch distances."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.branches.schemas import BranchRead


class BranchDistanceSet(BaseModel):
    """Body for recording or updating a distance between two branches."""

    model_config = ConfigDict(extra="forbid")

    from_branch_id: int = Field(ge=1, le=2147483647)
    to_branch_id: int = Field(ge=1, le=2147483647)

    # Must be positive. Zero would mean no distance, which is the self-distance
    # case refused separately. Negative distances have no physical meaning.
    distance_km: float = Field(gt=0)

    @model_validator(mode="after")
    def _branches_must_differ(self) -> "BranchDistanceSet":
        if self.from_branch_id == self.to_branch_id:
            raise ValueError(
                "from_branch_id and to_branch_id must be different; "
                "a branch has no distance to itself"
            )
        return self


class BranchDistanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    from_branch_id: int
    to_branch_id: int
    distance_km: float

    from_branch: BranchRead
    to_branch: BranchRead
