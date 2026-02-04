from flask import Blueprint, jsonify, request

from app.database import db
from app.models import Contact, Customer

contact_bp = Blueprint('contacts', __name__)


@contact_bp.route('', methods=['GET'])
def get_contacts():
    """获取所有联系人"""
    try:
        contacts = Contact.query.all()
        return jsonify([contact.to_dict() for contact in contacts]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@contact_bp.route('/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    """获取单个联系人"""
    try:
        contact = Contact.query.get_or_404(contact_id)
        return jsonify(contact.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@contact_bp.route('', methods=['POST'])
def create_contact():
    """创建新联系人"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or 'name' not in data or 'customer_id' not in data:
            return jsonify({'error': 'Name and customer_id are required'}), 400

        # 验证客户是否存在
        customer = Customer.query.get(data['customer_id'])
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        contact = Contact(
            customer_id=data['customer_id'],
            name=data.get('name'),
            position=data.get('position'),
            phone=data.get('phone'),
            email=data.get('email')
        )

        db.session.add(contact)
        db.session.commit()

        return jsonify(contact.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@contact_bp.route('/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    """更新联系人"""
    try:
        contact = Contact.query.get_or_404(contact_id)
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # 更新字段
        contact.name = data.get('name', contact.name)
        contact.position = data.get('position', contact.position)
        contact.phone = data.get('phone', contact.phone)
        contact.email = data.get('email', contact.email)

        db.session.commit()

        return jsonify(contact.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@contact_bp.route('/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    """删除联系人"""
    try:
        contact = Contact.query.get_or_404(contact_id)
        db.session.delete(contact)
        db.session.commit()

        return jsonify({'message': 'Contact deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
