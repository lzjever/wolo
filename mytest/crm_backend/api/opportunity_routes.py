"""
销售机会管理API路由
"""
from flask import Blueprint, jsonify, request
from services.opportunity_service import OpportunityService

opportunity_bp = Blueprint('opportunity', __name__)

@opportunity_bp.route('', methods=['GET'])
def get_opportunities():
    """获取所有销售机会"""
    try:
        customer_id = request.args.get('customer_id')
        stage = request.args.get('stage')

        if customer_id:
            opportunities = OpportunityService.get_opportunities_by_customer(int(customer_id))
        elif stage:
            opportunities = OpportunityService.get_opportunities_by_stage(stage)
        else:
            opportunities = OpportunityService.get_all_opportunities()

        return jsonify({
            'success': True,
            'data': [opportunity.to_dict() for opportunity in opportunities]
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@opportunity_bp.route('', methods=['POST'])
def create_opportunity():
    """创建新的销售机会"""
    try:
        data = request.get_json()

        # 验证必填字段
        if not data or 'customer_id' not in data or 'title' not in data:
            return jsonify({
                'success': False,
                'error': 'customer_id和title为必填项'
            }), 400

        opportunity = OpportunityService.create_opportunity(data)

        return jsonify({
            'success': True,
            'data': opportunity.to_dict(),
            'message': '销售机会创建成功'
        }), 201
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@opportunity_bp.route('/<int:opportunity_id>', methods=['GET'])
def get_opportunity(opportunity_id):
    """获取单个销售机会详情"""
    try:
        opportunity = OpportunityService.get_opportunity_by_id(opportunity_id)

        if not opportunity:
            return jsonify({
                'success': False,
                'error': '销售机会不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': opportunity.to_dict()
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@opportunity_bp.route('/<int:opportunity_id>', methods=['PUT'])
def update_opportunity(opportunity_id):
    """更新销售机会"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': '没有提供更新数据'
            }), 400

        opportunity = OpportunityService.update_opportunity(opportunity_id, data)

        if not opportunity:
            return jsonify({
                'success': False,
                'error': '销售机会不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': opportunity.to_dict(),
            'message': '销售机会更新成功'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@opportunity_bp.route('/<int:opportunity_id>', methods=['DELETE'])
def delete_opportunity(opportunity_id):
    """删除销售机会"""
    try:
        result = OpportunityService.delete_opportunity(opportunity_id)

        if not result:
            return jsonify({
                'success': False,
                'error': '销售机会不存在'
            }), 404

        return jsonify({
            'success': True,
            'message': '销售机会删除成功'
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@opportunity_bp.route('/pipeline', methods=['GET'])
def get_pipeline():
    """获取销售漏斗数据"""
    try:
        pipeline = OpportunityService.get_pipeline_value()

        return jsonify({
            'success': True,
            'data': pipeline
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
