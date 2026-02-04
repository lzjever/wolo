"""
销售机会数据模型
"""
from datetime import datetime

from database import db


class Opportunity(db.Model):
    """销售机会模型"""
    __tablename__ = 'opportunities'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    value = db.Column(db.Float)
    stage = db.Column(db.String(50), default='lead')  # lead, proposal, negotiation, closed, lost
    probability = db.Column(db.Integer, default=0)  # 0-100
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'title': self.title,
            'value': self.value,
            'stage': self.stage,
            'probability': self.probability,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<Opportunity {self.title} - {self.stage}>'
