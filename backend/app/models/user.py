from app.extensions import db
from app.utils.timezone import get_local_now
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    """User model with profiles and access control"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)  # Nullable for open access mode
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_local_now)
    last_login = db.Column(db.DateTime, nullable=True)

    # Profile information
    full_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)  # Path to profile image

    # Access permissions (for employees who need multiple section access)
    can_access_boutique = db.Column(db.Boolean, default=False)
    can_access_hardware = db.Column(db.Boolean, default=False)
    can_access_finance = db.Column(db.Boolean, default=False)
    can_access_customers = db.Column(db.Boolean, default=False)

    # Boutique branch assignment (for branch-specific employees)
    boutique_branch = db.Column(db.String(10), nullable=True)  # 'K', 'B', or None for all

    # Manager who created this account
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    def set_password(self, password):
        """Set hashed password"""
        if password:
            self.password_hash = generate_password_hash(password)
        else:
            self.password_hash = None

    def check_password(self, password):
        """Check if password matches"""
        if not self.password_hash:
            return True  # Open access mode
        return check_password_hash(self.password_hash, password)

    def has_access_to(self, section):
        """Check if user has access to a section"""
        if self.role == 'manager':
            return True
        if section == 'boutique' and (self.role == 'boutique' or self.can_access_boutique):
            return True
        if section == 'hardware' and (self.role == 'hardware' or self.can_access_hardware):
            return True
        if section == 'finance' and (self.role == 'finance' or self.can_access_finance):
            return True
        if section == 'customers' and (self.role == 'manager' or self.can_access_customers):
            return True
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'profile_picture': self.profile_picture,
            'is_active': self.is_active,
            'can_access_boutique': self.can_access_boutique,
            'can_access_hardware': self.can_access_hardware,
            'can_access_finance': self.can_access_finance,
            'can_access_customers': self.can_access_customers,
            'boutique_branch': self.boutique_branch,
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
