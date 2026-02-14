from app.extensions import db
from app.utils.timezone import get_local_now


class BoutiqueCategory(db.Model):
    __tablename__ = 'boutique_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }


class BoutiqueStock(db.Model):
    __tablename__ = 'boutique_stock'

    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('boutique_categories.id'))
    branch = db.Column(db.String(10), nullable=True)  # 'K', 'B', or None for shared
    quantity = db.Column(db.Integer, nullable=False)
    initial_quantity = db.Column(db.Integer, nullable=False)
    unit = db.Column(db.String(20), default='pieces')
    cost_price = db.Column(db.Numeric(12, 2), nullable=False)
    min_selling_price = db.Column(db.Numeric(12, 2), nullable=False)
    max_selling_price = db.Column(db.Numeric(12, 2), nullable=False)
    low_stock_threshold = db.Column(db.Integer)
    image_url = db.Column(db.String(500), nullable=True)
    for_hire = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)

    category = db.relationship('BoutiqueCategory', backref='stock_items')

    def to_dict(self):
        return {
            'id': self.id,
            'item_name': self.item_name,
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else None,
            'quantity': self.quantity,
            'initial_quantity': self.initial_quantity,
            'unit': self.unit,
            'cost_price': float(self.cost_price),
            'min_selling_price': float(self.min_selling_price),
            'max_selling_price': float(self.max_selling_price),
            'low_stock_threshold': self.low_stock_threshold,
            'image_url': self.image_url,
            'for_hire': self.for_hire,
            'is_active': self.is_active,
            'is_low_stock': self.quantity <= self.low_stock_threshold if self.low_stock_threshold else False
        }


class BoutiqueSale(db.Model):
    __tablename__ = 'boutique_sales'

    id = db.Column(db.Integer, primary_key=True)
    reference_number = db.Column(db.String(20), unique=True)
    branch = db.Column(db.String(10), nullable=True)  # 'K' or 'B'
    sale_date = db.Column(db.Date, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    payment_type = db.Column(db.String(10), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(12, 2), nullable=False)
    balance = db.Column(db.Numeric(12, 2), default=0)
    is_credit_cleared = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)
    deleted_at = db.Column(db.DateTime, nullable=True)

    customer = db.relationship('Customer', backref='boutique_sales', foreign_keys=[customer_id])
    items = db.relationship('BoutiqueSaleItem', backref='sale', lazy='dynamic')

    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'reference_number': self.reference_number,
            'sale_date': self.sale_date.isoformat(),
            'customer': self.customer.to_dict() if self.customer else None,
            'payment_type': self.payment_type,
            'total_amount': float(self.total_amount),
            'amount_paid': float(self.amount_paid),
            'balance': float(self.balance),
            'is_credit_cleared': self.is_credit_cleared,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_items:
            data['items'] = [item.to_dict() for item in self.items]
        return data


class BoutiqueSaleItem(db.Model):
    __tablename__ = 'boutique_sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('boutique_sales.id'))
    stock_id = db.Column(db.Integer, db.ForeignKey('boutique_stock.id'), nullable=True)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(12, 2), nullable=False)
    subtotal = db.Column(db.Numeric(12, 2), nullable=False)
    is_other_item = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)

    def to_dict(self):
        return {
            'id': self.id,
            'item_name': self.item_name,
            'quantity': self.quantity,
            'unit_price': float(self.unit_price),
            'subtotal': float(self.subtotal),
            'is_other_item': self.is_other_item
        }


class BoutiqueCreditPayment(db.Model):
    __tablename__ = 'boutique_credit_payments'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('boutique_sales.id'))
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    remaining_balance = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_now)

    def to_dict(self):
        return {
            'id': self.id,
            'payment_date': self.payment_date.isoformat(),
            'amount': float(self.amount),
            'remaining_balance': float(self.remaining_balance),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
