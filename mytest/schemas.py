"""Pydantic schemas for data validation"""
from datetime import datetime

from pydantic import BaseModel, Field


# Customer Schemas
class CustomerBase(BaseModel):
    """客户基础字段"""
    name: str = Field(..., min_length=1, max_length=200, description="客户名称")
    industry: str | None = Field(None, max_length=100, description="行业")
    company_size: str | None = Field(None, max_length=50, description="公司规模")
    website: str | None = Field(None, max_length=255, description="网站")
    phone: str | None = Field(None, max_length=50, description="电话")
    email: str | None = Field(None, max_length=100, description="邮箱")
    address: str | None = Field(None, description="地址")
    status: str = Field(default="active", description="状态: active, inactive, prospect")
    notes: str | None = Field(None, description="备注")


class CustomerCreate(CustomerBase):
    """创建客户的 Schema"""
    pass


class CustomerUpdate(BaseModel):
    """更新客户的 Schema（所有字段可选）"""
    name: str | None = Field(None, min_length=1, max_length=200)
    industry: str | None = Field(None, max_length=100)
    company_size: str | None = Field(None, max_length=50)
    website: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=100)
    address: str | None = None
    status: str | None = None
    notes: str | None = None


class CustomerResponse(CustomerBase):
    """客户响应 Schema"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Contact Schemas
class ContactBase(BaseModel):
    """联系人基础字段"""
    customer_id: int = Field(..., description="所属客户ID")
    name: str = Field(..., min_length=1, max_length=100, description="联系人姓名")
    title: str | None = Field(None, max_length=100, description="职位")
    department: str | None = Field(None, max_length=100, description="部门")
    phone: str | None = Field(None, max_length=50, description="电话")
    mobile: str | None = Field(None, max_length=50, description="手机")
    email: str | None = Field(None, max_length=100, description="邮箱")
    notes: str | None = Field(None, description="备注")


class ContactCreate(ContactBase):
    """创建联系人的 Schema"""
    pass


class ContactUpdate(BaseModel):
    """更新联系人的 Schema"""
    customer_id: int | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    title: str | None = Field(None, max_length=100)
    department: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=50)
    mobile: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=100)
    notes: str | None = None


class ContactResponse(ContactBase):
    """联系人响应 Schema"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Deal Schemas
class DealBase(BaseModel):
    """交易基础字段"""
    customer_id: int = Field(..., description="所属客户ID")
    deal_name: str = Field(..., min_length=1, max_length=200, description="交易名称")
    amount: float = Field(default=0.0, ge=0, description="交易金额")
    stage: str = Field(
        default="prospecting",
        description="阶段: prospecting, negotiation, won, lost"
    )
    probability: int = Field(
        default=50,
        ge=0,
        le=100,
        description="成交概率(0-100)"
    )
    expected_close_date: datetime | None = Field(None, description="预计成交日期")
    actual_close_date: datetime | None = Field(None, description="实际成交日期")
    description: str | None = Field(None, description="描述")


class DealCreate(DealBase):
    """创建交易的 Schema"""
    pass


class DealUpdate(BaseModel):
    """更新交易的 Schema"""
    customer_id: int | None = None
    deal_name: str | None = Field(None, min_length=1, max_length=200)
    amount: float | None = Field(None, ge=0)
    stage: str | None = None
    probability: int | None = Field(None, ge=0, le=100)
    expected_close_date: datetime | None = None
    actual_close_date: datetime | None = None
    description: str | None = None


class DealResponse(DealBase):
    """交易响应 Schema"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
