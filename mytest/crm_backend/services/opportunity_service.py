"""
销售机会业务逻辑服务
"""
from database import db
from models.opportunity import Opportunity


class OpportunityService:
    """销售机会服务类"""

    @staticmethod
    def create_opportunity(data):
        """创建新的销售机会"""
        opportunity = Opportunity(
            customer_id=data.get('customer_id'),
            title=data.get('title'),
            value=data.get('value'),
            stage=data.get('stage', 'lead'),
            probability=data.get('probability', 0)
        )
        db.session.add(opportunity)
        db.session.commit()
        db.session.refresh(opportunity)
        return opportunity

    @staticmethod
    def get_all_opportunities():
        """获取所有销售机会"""
        return Opportunity.query.all()

    @staticmethod
    def get_opportunity_by_id(opportunity_id):
        """根据ID获取销售机会"""
        return Opportunity.query.get(opportunity_id)

    @staticmethod
    def get_opportunities_by_customer(customer_id):
        """获取指定客户的所有销售机会"""
        return Opportunity.query.filter_by(customer_id=customer_id).order_by(
            Opportunity.created_at.desc()
        ).all()

    @staticmethod
    def get_opportunities_by_stage(stage):
        """根据阶段获取销售机会"""
        return Opportunity.query.filter_by(stage=stage).all()

    @staticmethod
    def update_opportunity(opportunity_id, data):
        """更新销售机会"""
        opportunity = Opportunity.query.get(opportunity_id)
        if not opportunity:
            return None

        if 'title' in data:
            opportunity.title = data['title']
        if 'value' in data:
            opportunity.value = data['value']
        if 'stage' in data:
            opportunity.stage = data['stage']
        if 'probability' in data:
            opportunity.probability = data['probability']

        db.session.commit()
        db.session.refresh(opportunity)
        return opportunity

    @staticmethod
    def delete_opportunity(opportunity_id):
        """删除销售机会"""
        opportunity = Opportunity.query.get(opportunity_id)
        if not opportunity:
            return False

        db.session.delete(opportunity)
        db.session.commit()
        return True

    @staticmethod
    def get_pipeline_value():
        """获取销售漏斗总价值"""
        stages = ['lead', 'proposal', 'negotiation', 'closed']
        pipeline = {}
        total_value = 0

        for stage in stages:
            opportunities = Opportunity.query.filter_by(stage=stage).all()
            stage_value = sum(op.value or 0 for op in opportunities)
            pipeline[stage] = {
                'count': len(opportunities),
                'value': stage_value
            }
            total_value += stage_value

        pipeline['total'] = total_value
        return pipeline
