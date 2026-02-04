"""SQLAlchemy 数据模型"""
from datetime import datetime

from database import Base
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship


class Customer(Base):
    """客户模型"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    industry = Column(String(100))
    company_size = Column(String(50))
    website = Column(String(255))
    phone = Column(String(50))
    email = Column(String(100))
    address = Column(Text)
    status = Column(String(20), default="active")  # active, inactive, prospect
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    contacts = relationship("Contact", back_populates="customer", cascade="all, delete-orphan")
    deals = relationship("Deal", back_populates="customer", cascade="all, delete-orphan")


class Contact(Base):
    """联系人模型"""
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    name = Column(String(100), nullable=False)
    title = Column(String(100))
    department = Column(String(100))
    phone = Column(String(50))
    mobile = Column(String(50))
    email = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    customer = relationship("Customer", back_populates="contacts")


class Deal(Base):
    """交易/订单模型"""
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    deal_name = Column(String(200), nullable=False)
    amount = Column(Float, default=0.0)
    stage = Column(String(50), default="prospecting")  # prospecting, negotiation, won, lost
    probability = Column(Integer, default=50)  # 成交概率百分比
    expected_close_date = Column(DateTime)
    actual_close_date = Column(DateTime)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    customer = relationship("Customer", back_populates="deals")
