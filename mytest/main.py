"""CRM Backend - FastAPI Application"""

import crud
import database
import schemas
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# 创建 FastAPI 应用
app = FastAPI(
    title="CRM Backend API",
    description="简易客户关系管理系统后端",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 事件处理 ====================
@app.on_event("startup")
def startup_event():
    """应用启动时初始化数据库"""
    database.init_db()


# ==================== 根路径 ====================
@app.get("/")
def read_root():
    """根路径"""
    return {
        "message": "CRM Backend API",
        "version": "1.0.0",
        "docs": "/docs"
    }


# ==================== Customer 路由 ====================
@app.get("/customers/", response_model=list[schemas.CustomerResponse])
def read_customers(
    skip: int = Query(0, ge=0, description="跳过记录数"),
    limit: int = Query(100, ge=1, le=100, description="返回记录数"),
    status: str = Query(None, description="状态筛选"),
    db: Session = Depends(database.get_db)
):
    """获取客户列表"""
    customers = crud.get_customers(db, skip=skip, limit=limit, status=status)
    return customers


@app.get("/customers/{customer_id}", response_model=schemas.CustomerResponse)
def read_customer(customer_id: int, db: Session = Depends(database.get_db)):
    """获取单个客户"""
    customer = crud.get_customer(db, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="客户不存在")
    return customer


@app.post("/customers/", response_model=schemas.CustomerResponse, status_code=201)
def create_customer(
    customer: schemas.CustomerCreate,
    db: Session = Depends(database.get_db)
):
    """创建新客户"""
    return crud.create_customer(db, customer)


@app.put("/customers/{customer_id}", response_model=schemas.CustomerResponse)
def update_customer(
    customer_id: int,
    customer: schemas.CustomerUpdate,
    db: Session = Depends(database.get_db)
):
    """更新客户信息"""
    updated_customer = crud.update_customer(db, customer_id, customer)
    if updated_customer is None:
        raise HTTPException(status_code=404, detail="客户不存在")
    return updated_customer


@app.delete("/customers/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(database.get_db)):
    """删除客户"""
    success = crud.delete_customer(db, customer_id)
    if not success:
        raise HTTPException(status_code=404, detail="客户不存在")
    return None


# ==================== Contact 路由 ====================
@app.get("/contacts/", response_model=list[schemas.ContactResponse])
def read_contacts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    customer_id: int = Query(None, description="筛选特定客户的联系人"),
    db: Session = Depends(database.get_db)
):
    """获取联系人列表"""
    contacts = crud.get_contacts(db, skip=skip, limit=limit, customer_id=customer_id)
    return contacts


@app.get("/contacts/{contact_id}", response_model=schemas.ContactResponse)
def read_contact(contact_id: int, db: Session = Depends(database.get_db)):
    """获取单个联系人"""
    contact = crud.get_contact(db, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")
    return contact


@app.post("/contacts/", response_model=schemas.ContactResponse, status_code=201)
def create_contact(
    contact: schemas.ContactCreate,
    db: Session = Depends(database.get_db)
):
    """创建新联系人"""
    # 确保客户存在
    customer = crud.get_customer(db, contact.customer_id)
    if customer is None:
        raise HTTPException(status_code=400, detail="客户不存在")
    return crud.create_contact(db, contact)


@app.put("/contacts/{contact_id}", response_model=schemas.ContactResponse)
def update_contact(
    contact_id: int,
    contact: schemas.ContactUpdate,
    db: Session = Depends(database.get_db)
):
    """更新联系人信息"""
    # 如果包含 customer_id，确保客户存在
    if contact.customer_id is not None:
        customer = crud.get_customer(db, contact.customer_id)
        if customer is None:
            raise HTTPException(status_code=400, detail="客户不存在")

    updated_contact = crud.update_contact(db, contact_id, contact)
    if updated_contact is None:
        raise HTTPException(status_code=404, detail="联系人不存在")
    return updated_contact


@app.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: int, db: Session = Depends(database.get_db)):
    """删除联系人"""
    success = crud.delete_contact(db, contact_id)
    if not success:
        raise HTTPException(status_code=404, detail="联系人不存在")
    return None


# ==================== Deal 路由 ====================
@app.get("/deals/", response_model=list[schemas.DealResponse])
def read_deals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    customer_id: int = Query(None, description="筛选特定客户的交易"),
    stage: str = Query(None, description="交易阶段筛选"),
    db: Session = Depends(database.get_db)
):
    """获取交易列表"""
    deals = crud.get_deals(db, skip=skip, limit=limit, customer_id=customer_id, stage=stage)
    return deals


@app.get("/deals/{deal_id}", response_model=schemas.DealResponse)
def read_deal(deal_id: int, db: Session = Depends(database.get_db)):
    """获取单个交易"""
    deal = crud.get_deal(db, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="交易不存在")
    return deal


@app.post("/deals/", response_model=schemas.DealResponse, status_code=201)
def create_deal(
    deal: schemas.DealCreate,
    db: Session = Depends(database.get_db)
):
    """创建新交易"""
    # 确保客户存在
    customer = crud.get_customer(db, deal.customer_id)
    if customer is None:
        raise HTTPException(status_code=400, detail="客户不存在")
    return crud.create_deal(db, deal)


@app.put("/deals/{deal_id}", response_model=schemas.DealResponse)
def update_deal(
    deal_id: int,
    deal: schemas.DealUpdate,
    db: Session = Depends(database.get_db)
):
    """更新交易信息"""
    # 如果包含 customer_id，确保客户存在
    if deal.customer_id is not None:
        customer = crud.get_customer(db, deal.customer_id)
        if customer is None:
            raise HTTPException(status_code=400, detail="客户不存在")

    updated_deal = crud.update_deal(db, deal_id, deal)
    if updated_deal is None:
        raise HTTPException(status_code=404, detail="交易不存在")
    return updated_deal


@app.delete("/deals/{deal_id}", status_code=204)
def delete_deal(deal_id: int, db: Session = Depends(database.get_db)):
    """删除交易"""
    success = crud.delete_deal(db, deal_id)
    if not success:
        raise HTTPException(status_code=404, detail="交易不存在")
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
