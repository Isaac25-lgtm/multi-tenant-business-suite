from app.extensions import db
from datetime import datetime
from app.utils.timezone import get_local_now
import bcrypt


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('manager', 'employee', name='user_role'), nullable=False)
    assigned_business = db.Column(db.Enum('boutique', 'hardware', 'finances', 'all', name='business_type'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    can_backdate = db.Column(db.Boolean, default=False)
    backdate_limit = db.Column(db.Integer, default=1)  # Days
    can_edit = db.Column(db.Boolean, default=True)
    can_delete = db.Column(db.Boolean, default=True)
    can_clear_credits = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'role': self.role,
            'assigned_business': self.assigned_business,
            'is_active': self.is_active,
            'can_backdate': self.can_backdate,
            'backdate_limit': self.backdate_limit,
            'can_edit': self.can_edit,
            'can_delete': self.can_delete,
            'can_clear_credits': self.can_clear_credits,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
