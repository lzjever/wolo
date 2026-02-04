from flask import Blueprint, jsonify, request

from app.database import db
from app.models import Customer

customer_bp = Blueprint('customers', __name__)


@customer_bp.route('', methods=['GET'])
def get_customers():
    """获取所有客户"""
    try:
        customers = Customer.query.all()
        return jsonify([customer.to_dict() for customer in customers]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@customer_bp.route('/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """获取单个客户"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        return jsonify(customer.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@customer_bp.route('', methods=['POST'])
def create_customer():
    """创建新客户"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or 'name' not in data:
            return jsonify({'error': 'Name is required'}), 400

        customer = Customer(
            name=data.get('name'),
            industry=data.get('industry'),
            website=data.get('website'),
            phone=data.get('phone'),
            email=data.get('email'),
            address=data.get('address')
        )

        db.session.add(customer)
        db.session.commit()

        return jsonify(customer.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@customer_bp.route('/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    """更新客户"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # 更新字段
        customer.name = data.get('name', customer.name)
        customer.industry = data.get('industry', customer.industry)
        customer.website = data.get('website', customer.website)
        customer.phone = data.get('phone', customer.phone)
        customer.email = data.get('email', customer.email)
        customer.address = data.get('address', customer.address)

        db.session.commit()

        return jsonify(customer.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@customer_bp.route('/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    """删除客户"""
    try:
        customer = Customer.query.get_or_404(customer_id)
        db.session.delete(customer)
        db.session.commit()

        return jsonify({'message': 'Customer deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
