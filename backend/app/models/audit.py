from app.extensions import db
from datetime import datetime


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.Enum('create', 'update', 'delete', 'login', 'logout', 'view', name='audit_action'), nullable=False)
    module = db.Column(db.Enum('boutique', 'hardware', 'finances', 'auth', 'settings', name='audit_module'), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)
    description = db.Column(db.String(500), nullable=False)
    ip_address = db.Column(db.String(50), nullable=True)
    is_flagged = db.Column(db.Boolean, default=False)
    flag_reason = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', foreign_keys=[user_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_name': self.user.name if self.user else None,
            'action': self.action,
            'module': self.module,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'description': self.description,
            'is_flagged': self.is_flagged,
            'flag_reason': self.flag_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
