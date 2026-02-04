from datetime import datetime

from pydantic import BaseModel, Field


class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    industry: str | None = Field(None, max_length=100)
    status: str = Field("potential", regex="^(potential|active|closed)$")
    email: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=1000)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    industry: str | None = Field(None, max_length=100)
    status: str | None = Field(None, regex="^(potential|active|closed)$")
    email: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=1000)


class ContactSchema(BaseModel):
    id: int
    name: str
    position: str | None
    email: str | None
    phone: str | None

    class Config:
        from_attributes = True


class OpportunitySchema(BaseModel):
    id: int
    title: str
    value: int | None
    stage: str
    expected_close_date: datetime | None

    class Config:
        from_attributes = True


class Customer(CustomerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerWithRelations(Customer):
    contacts: list[ContactSchema] = []
    opportunities: list[OpportunitySchema] = []
