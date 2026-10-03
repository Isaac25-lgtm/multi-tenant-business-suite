from app.extensions import db
from app.utils.timezone import get_local_now


class Expense(db.Model):
    """An operating expense. Needed before net profit can be reported truthfully."""
    __tablename__ = 'expenses'

    CATEGORIES = {
        'rent': 'Rent',
        'salaries_wages': 'Salaries & wages',
        'transport': 'Transport',
        'utilities': 'Utilities',
        'communications': 'Airtime & internet',
        'repairs_maintenance': 'Repairs & maintenance',
        'taxes_fees': 'Taxes & fees',
        'professional_services': 'Professional services',
        'marketing': 'Marketing',
        'inventory_related': 'Inventory related',
        'other': 'Other',
    }
    BUSINESS_UNITS = {
        'boutique': 'Boutique',
        'hardware': 'Hardware',
        'finance': 'Finance',
        'shared': 'Shared (whole company)',
    }
    PAYMENT_METHODS = {
        'cash': 'Cash',
        'mobile_money': 'Mobile money',
        'bank': 'Bank',
        'other': 'Other',
    }

    id = db.Column(db.Integer, primary_key=True)
    expense_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(40), nullable=False)
    business_unit = db.Column(db.String(20), nullable=False, default='shared')
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    payment_method = db.Column(db.String(20), nullable=True)
    reference = db.Column(db.String(100), nullable=True)
    created_by = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_by = db.Column(db.String(50), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deletion_reason = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.CheckConstraint('amount > 0', name='ck_expenses_positive_amount'),
    )

    @property
    def category_label(self):
        return self.CATEGORIES.get(self.category, self.category)

    @property
    def business_unit_label(self):
        return self.BUSINESS_UNITS.get(self.business_unit, self.business_unit)
