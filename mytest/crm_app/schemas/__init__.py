from schemas.contact import Contact as ContactSchema
from schemas.contact import ContactCreate, ContactUpdate
from schemas.customer import Customer as CustomerSchema
from schemas.customer import CustomerCreate, CustomerUpdate, CustomerWithRelations
from schemas.opportunity import Opportunity as OpportunitySchema
from schemas.opportunity import OpportunityCreate, OpportunityUpdate

__all__ = [
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerSchema",
    "CustomerWithRelations",
    "ContactCreate",
    "ContactUpdate",
    "ContactSchema",
    "OpportunityCreate",
    "OpportunityUpdate",
    "OpportunitySchema",
]
