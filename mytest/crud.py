"""CRUD operations for all models"""

import models
import schemas
from sqlalchemy.orm import Session


# ==================== Customer CRUD ====================
def get_customer(db: Session, customer_id: int) -> models.Customer | None:
    """获取单个客户"""
    return db.query(models.Customer).filter(models.Customer.id == customer_id).first()


def get_customers(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: str | None = None
) -> list[models.Customer]:
    """获取客户列表"""
    query = db.query(models.Customer)
    if status:
        query = query.filter(models.Customer.status == status)
    return query.offset(skip).limit(limit).all()


def create_customer(db: Session, customer: schemas.CustomerCreate) -> models.Customer:
    """创建客户"""
    db_customer = models.Customer(**customer.dict())
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer


def update_customer(
    db: Session,
    customer_id: int,
    customer: schemas.CustomerUpdate
) -> models.Customer | None:
    """更新客户"""
    db_customer = get_customer(db, customer_id)
    if db_customer:
        update_data = customer.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_customer, key, value)
        db.commit()
        db.refresh(db_customer)
    return db_customer


def delete_customer(db: Session, customer_id: int) -> bool:
    """删除客户"""
    db_customer = get_customer(db, customer_id)
    if db_customer:
        db.delete(db_customer)
        db.commit()
        return True
    return False


# ==================== Contact CRUD ====================
def get_contact(db: Session, contact_id: int) -> models.Contact | None:
    """获取单个联系人"""
    return db.query(models.Contact).filter(models.Contact.id == contact_id).first()


def get_contacts(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    customer_id: int | None = None
) -> list[models.Contact]:
    """获取联系人列表"""
    query = db.query(models.Contact)
    if customer_id:
        query = query.filter(models.Contact.customer_id == customer_id)
    return query.offset(skip).limit(limit).all()


def create_contact(db: Session, contact: schemas.ContactCreate) -> models.Contact:
    """创建联系人"""
    db_contact = models.Contact(**contact.dict())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact


def update_contact(
    db: Session,
    contact_id: int,
    contact: schemas.ContactUpdate
) -> models.Contact | None:
    """更新联系人"""
    db_contact = get_contact(db, contact_id)
    if db_contact:
        update_data = contact.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_contact, key, value)
        db.commit()
        db.refresh(db_contact)
    return db_contact


def delete_contact(db: Session, contact_id: int) -> bool:
    """删除联系人"""
    db_contact = get_contact(db, contact_id)
    if db_contact:
        db.delete(db_contact)
        db.commit()
        return True
    return False


# ==================== Deal CRUD ====================
def get_deal(db: Session, deal_id: int) -> models.Deal | None:
    """获取单个交易"""
    return db.query(models.Deal).filter(models.Deal.id == deal_id).first()


def get_deals(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    customer_id: int | None = None,
    stage: str | None = None
) -> list[models.Deal]:
    """获取交易列表"""
    query = db.query(models.Deal)
    if customer_id:
        query = query.filter(models.Deal.customer_id == customer_id)
    if stage:
        query = query.filter(models.Deal.stage == stage)
    return query.offset(skip).limit(limit).all()


def create_deal(db: Session, deal: schemas.DealCreate) -> models.Deal:
    """创建交易"""
    db_deal = models.Deal(**deal.dict())
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)
    return db_deal


def update_deal(
    db: Session,
    deal_id: int,
    deal: schemas.DealUpdate
) -> models.Deal | None:
    """更新交易"""
    db_deal = get_deal(db, deal_id)
    if db_deal:
        update_data = deal.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_deal, key, value)
        db.commit()
        db.refresh(db_deal)
    return db_deal


def delete_deal(db: Session, deal_id: int) -> bool:
    """删除交易"""
    db_deal = get_deal(db, deal_id)
    if db_deal:
        db.delete(db_deal)
        db.commit()
        return True
    return False
