from app.extensions import db
from app.utils.timezone import get_local_now


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    nin = db.Column(db.String(20), nullable=True)
    business_type = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=get_local_now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'address': self.address,
            'nin': self.nin,
            'business_type': self.business_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
