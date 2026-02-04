"""
互动记录业务逻辑服务
"""
from database import db
from models.interaction import Interaction


class InteractionService:
    """互动记录服务类"""

    @staticmethod
    def create_interaction(data):
        """创建新的互动记录"""
        interaction = Interaction(
            customer_id=data.get('customer_id'),
            interaction_type=data.get('interaction_type'),
            notes=data.get('notes')
        )
        db.session.add(interaction)
        db.session.commit()
        db.session.refresh(interaction)
        return interaction

    @staticmethod
    def get_all_interactions():
        """获取所有互动记录"""
        return Interaction.query.all()

    @staticmethod
    def get_interaction_by_id(interaction_id):
        """根据ID获取互动记录"""
        return Interaction.query.get(interaction_id)

    @staticmethod
    def get_interactions_by_customer(customer_id):
        """获取指定客户的所有互动记录"""
        return Interaction.query.filter_by(customer_id=customer_id).order_by(
            Interaction.created_at.desc()
        ).all()

    @staticmethod
    def update_interaction(interaction_id, data):
        """更新互动记录"""
        interaction = Interaction.query.get(interaction_id)
        if not interaction:
            return None

        if 'interaction_type' in data:
            interaction.interaction_type = data['interaction_type']
        if 'notes' in data:
            interaction.notes = data['notes']

        db.session.commit()
        db.session.refresh(interaction)
        return interaction

    @staticmethod
    def delete_interaction(interaction_id):
        """删除互动记录"""
        interaction = Interaction.query.get(interaction_id)
        if not interaction:
            return False

        db.session.delete(interaction)
        db.session.commit()
        return True
