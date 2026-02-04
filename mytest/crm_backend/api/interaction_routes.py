"""
互动记录管理API路由
"""
from flask import Blueprint, jsonify, request
from services.interaction_service import InteractionService

interaction_bp = Blueprint('interaction', __name__)

@interaction_bp.route('', methods=['GET'])
def get_interactions():
    """获取所有互动记录"""
    try:
        customer_id = request.args.get('customer_id')

        if customer_id:
            interactions = InteractionService.get_interactions_by_customer(int(customer_id))
        else:
            interactions = InteractionService.get_all_interactions()

        return jsonify({
            'success': True,
            'data': [interaction.to_dict() for interaction in interactions]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@interaction_bp.route('', methods=['POST'])
def create_interaction():
    """创建新的互动记录"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or 'customer_id' not in data or 'interaction_type' not in data:
            return jsonify({
                'success': False,
                'error': 'customer_id和interaction_type为必填项'
            }), 400

        interaction = InteractionService.create_interaction(data)

        return jsonify({
            'success': True,
            'data': interaction.to_dict(),
            'message': '互动记录创建成功'
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@interaction_bp.route('/<int:interaction_id>', methods=['GET'])
def get_interaction(interaction_id):
    """获取单个互动记录详情"""
    try:
        interaction = InteractionService.get_interaction_by_id(interaction_id)

        if not interaction:
            return jsonify({
                'success': False,
                'error': '互动记录不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': interaction.to_dict()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@interaction_bp.route('/<int:interaction_id>', methods=['PUT'])
def update_interaction(interaction_id):
    """更新互动记录"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': '没有提供更新数据'
            }), 400

        interaction = InteractionService.update_interaction(interaction_id, data)

        if not interaction:
            return jsonify({
                'success': False,
                'error': '互动记录不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': interaction.to_dict(),
            'message': '互动记录更新成功'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@interaction_bp.route('/<int:interaction_id>', methods=['DELETE'])
def delete_interaction(interaction_id):
    """删除互动记录"""
    try:
        result = InteractionService.delete_interaction(interaction_id)

        if not result:
            return jsonify({
                'success': False,
                'error': '互动记录不存在'
            }), 404

        return jsonify({
            'success': True,
            'message': '互动记录删除成功'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
