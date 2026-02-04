"""
互动记录数据模型
"""
from datetime import datetime

from database import db


class Interaction(db.Model):
    """互动记录模型"""
    __tablename__ = 'interactions'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    interaction_type = db.Column(db.String(50), nullable=False)  # call, email, meeting, other
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'interaction_type': self.interaction_type,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<Interaction {self.interaction_type} - {self.created_at}>'
