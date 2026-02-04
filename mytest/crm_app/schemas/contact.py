from datetime import datetime

from pydantic import BaseModel, Field


class ContactBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    position: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=500)


class ContactCreate(ContactBase):
    customer_id: int


class ContactUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=150)
    position: str | None = Field(None, max_length=100)
    email: str | None = Field(None, max_length=150)
    phone: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=500)


class Contact(ContactBase):
    id: int
    customer_id: int
    created_at: datetime

    class Config:
        from_attributes = True
