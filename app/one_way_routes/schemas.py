"""Request and response shapes for one-way route enablement."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OneWayRouteEnable(BaseModel):
    # `extra="forbid"` is the project-wide rule: an unexpected field is refused,
    # never silently ignored. Without it this route accepted a body carrying a
    # `relocation_fee` and answered 200 having thrown it away, which is exactly
    # the failure the convention exists to prevent -- the caller believes they
    # set something they did not.
    model_config = ConfigDict(extra="forbid")

    # Bounded above as well as below. Without the upper bound an id larger than
    # an integer primary key can hold reaches PostgreSQL and raises
    # NumericValueOutOfRange, which surfaces as a 500. The sibling schemas in
    # `branch_distances` and `quotations` already carry this bound; this one was
    # the only request shape in the service missing it.
    from_branch_id: int = Field(ge=1, le=2147483647)
    to_branch_id: int = Field(ge=1, le=2147483647)

    @model_validator(mode="after")
    def branches_must_differ(self) -> "OneWayRouteEnable":
        if self.from_branch_id == self.to_branch_id:
            raise ValueError("from_branch_id and to_branch_id must be different.")
        return self


class BranchSummary(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class OneWayRouteRead(BaseModel):
    from_branch: BranchSummary
    to_branch: BranchSummary

    model_config = {"from_attributes": True}
