from flask import Blueprint, jsonify, request

from app.database import db
from app.models import Customer, Deal

deal_bp = Blueprint('deals', __name__)


@deal_bp.route('', methods=['GET'])
def get_deals():
    """获取所有交易"""
    try:
        deals = Deal.query.all()
        return jsonify([deal.to_dict() for deal in deals]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deal_bp.route('/<int:deal_id>', methods=['GET'])
def get_deal(deal_id):
    """获取单个交易"""
    try:
        deal = Deal.query.get_or_404(deal_id)
        return jsonify(deal.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@deal_bp.route('', methods=['POST'])
def create_deal():
    """创建新交易"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or 'title' not in data or 'customer_id' not in data:
            return jsonify({'error': 'Title and customer_id are required'}), 400

        # 验证客户是否存在
        customer = Customer.query.get(data['customer_id'])
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        # 验证状态
        valid_statuses = ['lead', 'opportunity', 'negotiation', 'won', 'lost']
        status = data.get('status', 'lead')
        if status not in valid_statuses:
            return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400

        deal = Deal(
            customer_id=data['customer_id'],
            title=data.get('title'),
            description=data.get('description'),
            amount=data.get('amount', 0.0),
            status=status
        )

        db.session.add(deal)
        db.session.commit()

        return jsonify(deal.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@deal_bp.route('/<int:deal_id>', methods=['PUT'])
def update_deal(deal_id):
    """更新交易"""
    try:
        deal = Deal.query.get_or_404(deal_id)
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # 验证状态（如果提供）
        if 'status' in data:
            valid_statuses = ['lead', 'opportunity', 'negotiation', 'won', 'lost']
            if data['status'] not in valid_statuses:
                return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400

        # 更新字段
        deal.title = data.get('title', deal.title)
        deal.description = data.get('description', deal.description)
        deal.amount = data.get('amount', deal.amount)
        deal.status = data.get('status', deal.status)

        db.session.commit()

        return jsonify(deal.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@deal_bp.route('/<int:deal_id>', methods=['DELETE'])
def delete_deal(deal_id):
    """删除交易"""
    try:
        deal = Deal.query.get_or_404(deal_id)
        db.session.delete(deal)
        db.session.commit()

        return jsonify({'message': 'Deal deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
