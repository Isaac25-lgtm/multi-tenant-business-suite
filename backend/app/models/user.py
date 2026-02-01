from app.extensions import db
from app.utils.timezone import get_local_now


class User(db.Model):
    """Simple user model for tracking who does what"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    role = db.Column(db.Enum('manager', 'boutique', 'hardware', 'finance', name='user_role'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_local_now)
    last_login = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class AuditLog(db.Model):
    """Track all actions in the system"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(50), nullable=False)  # boutique, hardware, finance, customers
    action = db.Column(db.String(50), nullable=False)   # create, update, delete, view
    entity = db.Column(db.String(50), nullable=False)   # stock, sale, loan, etc.
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)         # JSON with old/new values
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=get_local_now)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'section': self.section,
            'action': self.action,
            'entity': self.entity,
            'entity_id': self.entity_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
