"""
客户管理API路由
"""
from flask import Blueprint, jsonify, request
from services.customer_service import CustomerService

customer_bp = Blueprint('customer', __name__)

@customer_bp.route('', methods=['GET'])
def get_customers():
    """获取所有客户"""
    try:
        keyword = request.args.get('search')
        if keyword:
            customers = CustomerService.search_customers(keyword)
        else:
            customers = CustomerService.get_all_customers()

        return jsonify({
            'success': True,
            'data': [customer.to_dict() for customer in customers]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@customer_bp.route('', methods=['POST'])
def create_customer():
    """创建新客户"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or 'name' not in data:
            return jsonify({
                'success': False,
                'error': '客户名称为必填项'
            }), 400

        customer = CustomerService.create_customer(data)

        return jsonify({
            'success': True,
            'data': customer.to_dict(),
            'message': '客户创建成功'
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@customer_bp.route('/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """获取单个客户详情"""
    try:
        customer = CustomerService.get_customer_by_id(customer_id)

        if not customer:
            return jsonify({
                'success': False,
                'error': '客户不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': customer.to_dict()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@customer_bp.route('/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    """更新客户信息"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': '没有提供更新数据'
            }), 400

        customer = CustomerService.update_customer(customer_id, data)

        if not customer:
            return jsonify({
                'success': False,
                'error': '客户不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': customer.to_dict(),
            'message': '客户更新成功'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@customer_bp.route('/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    """删除客户"""
    try:
        result = CustomerService.delete_customer(customer_id)

        if not result:
            return jsonify({
                'success': False,
                'error': '客户不存在'
            }), 404

        return jsonify({
            'success': True,
            'message': '客户删除成功'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
