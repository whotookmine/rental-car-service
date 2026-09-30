from pydantic import BaseModel, Field, model_validator


class OneWayRouteEnable(BaseModel):
    from_branch_id: int = Field(ge=1)
    to_branch_id: int = Field(ge=1)

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
