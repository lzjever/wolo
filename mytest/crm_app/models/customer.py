from datetime import datetime

from database import Base
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    industry = Column(String(100), nullable=True)
    status = Column(String(50), default="potential", nullable=False)
    email = Column(String(150), nullable=True, unique=True, index=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    contacts = relationship("Contact", back_populates="customer", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="customer", cascade="all, delete-orphan")
