"""
客户业务逻辑服务
"""
from database import db
from models.customer import Customer


class CustomerService:
    """客户服务类"""

    @staticmethod
    def create_customer(data):
        """创建新客户"""
        customer = Customer(
            name=data.get('name'),
            company=data.get('company'),
            email=data.get('email'),
            phone=data.get('phone'),
            status=data.get('status', 'active')
        )
        db.session.add(customer)
        db.session.commit()
        db.session.refresh(customer)
        return customer

    @staticmethod
    def get_all_customers():
        """获取所有客户"""
        return Customer.query.all()

    @staticmethod
    def get_customer_by_id(customer_id):
        """根据ID获取客户"""
        return Customer.query.get(customer_id)

    @staticmethod
    def update_customer(customer_id, data):
        """更新客户信息"""
        customer = Customer.query.get(customer_id)
        if not customer:
            return None

        if 'name' in data:
            customer.name = data['name']
        if 'company' in data:
            customer.company = data['company']
        if 'email' in data:
            customer.email = data['email']
        if 'phone' in data:
            customer.phone = data['phone']
        if 'status' in data:
            customer.status = data['status']

        db.session.commit()
        db.session.refresh(customer)
        return customer

    @staticmethod
    def delete_customer(customer_id):
        """删除客户"""
        customer = Customer.query.get(customer_id)
        if not customer:
            return False

        db.session.delete(customer)
        db.session.commit()
        return True

    @staticmethod
    def search_customers(keyword):
        """搜索客户"""
        return Customer.query.filter(
            db.or_(
                Customer.name.like(f'%{keyword}%'),
                Customer.company.like(f'%{keyword}%'),
                Customer.email.like(f'%{keyword}%')
            )
        ).all()
