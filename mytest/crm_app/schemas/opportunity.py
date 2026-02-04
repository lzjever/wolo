from datetime import datetime

from pydantic import BaseModel, Field


class OpportunityBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    value: int | None = Field(None, ge=0)
    stage: str = Field(
        "lead",
        regex="^(lead|qualified|proposal|negotiation|won|lost)$"
    )
    expected_close_date: datetime | None = None
    notes: str | None = Field(None, max_length=1000)


class OpportunityCreate(OpportunityBase):
    customer_id: int


class OpportunityUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    value: int | None = Field(None, ge=0)
    stage: str | None = Field(
        None,
        regex="^(lead|qualified|proposal|negotiation|won|lost)$"
    )
    expected_close_date: datetime | None = None
    notes: str | None = Field(None, max_length=1000)


class Opportunity(OpportunityBase):
    id: int
    customer_id: int
    created_at: datetime

    class Config:
        from_attributes = True
