from app.extensions import db
from app.utils.timezone import get_local_now


class LoanClient(db.Model):
    """Loan clients (borrowers)"""
    __tablename__ = 'loan_clients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    nin = db.Column(db.String(20), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_local_now)

    loans = db.relationship('Loan', backref='client', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'nin': self.nin,
            'phone': self.phone,
            'address': self.address,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Loan(db.Model):
    """Individual loans"""
    __tablename__ = 'loans'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('loan_clients.id'), nullable=False)
    principal = db.Column(db.Numeric(12, 2), nullable=False)
    interest_rate = db.Column(db.Numeric(5, 2), nullable=False)
    interest_amount = db.Column(db.Numeric(12, 2), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(12, 2), default=0)
    balance = db.Column(db.Numeric(12, 2), nullable=False)
    duration_weeks = db.Column(db.Integer, nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum('active', 'overdue', 'due_soon', 'paid', 'renewed', name='loan_status'), default='active')
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)
    deleted_at = db.Column(db.DateTime, nullable=True)

    payments = db.relationship('LoanPayment', backref='loan', lazy='dynamic')
    documents = db.relationship('LoanDocument', backref='loan', lazy='dynamic',
                               primaryjoin='Loan.id==LoanDocument.loan_id')

    def to_dict(self, include_payments=False):
        data = {
            'id': self.id,
            'client_id': self.client_id,
            'client': self.client.to_dict() if self.client else None,
            'principal': float(self.principal),
            'interest_rate': float(self.interest_rate),
            'interest_amount': float(self.interest_amount),
            'total_amount': float(self.total_amount),
            'amount_paid': float(self.amount_paid),
            'balance': float(self.balance),
            'duration_weeks': self.duration_weeks,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_payments:
            data['payments'] = [p.to_dict() for p in self.payments.order_by(LoanPayment.payment_date.desc())]
        return data


class LoanPayment(db.Model):
    """Loan payments"""
    __tablename__ = 'loan_payments'

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loans.id'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    balance_after = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.String(200), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)

    def to_dict(self):
        return {
            'id': self.id,
            'loan_id': self.loan_id,
            'client_name': self.loan.client.name if self.loan and self.loan.client else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'amount': float(self.amount),
            'balance_after': float(self.balance_after),
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class GroupLoan(db.Model):
    """Group loans"""
    __tablename__ = 'group_loans'

    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False)
    member_count = db.Column(db.Integer, nullable=False)
    members_json = db.Column(db.Text, nullable=True)  # JSON string storing member details
    principal = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    interest_rate = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    interest_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    amount_per_period = db.Column(db.Numeric(12, 2), nullable=False)
    total_periods = db.Column(db.Integer, nullable=False)
    period_type = db.Column(db.String(20), nullable=False, default='monthly')
    periods_paid = db.Column(db.Integer, default=0)
    amount_paid = db.Column(db.Numeric(12, 2), default=0)
    balance = db.Column(db.Numeric(12, 2), nullable=False)
    issue_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.Enum('active', 'overdue', 'paid', name='group_loan_status'), default='active')
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)

    payments = db.relationship('GroupLoanPayment', backref='group_loan', lazy='dynamic')
    documents = db.relationship('LoanDocument', backref='group_loan', lazy='dynamic',
                               primaryjoin='GroupLoan.id==LoanDocument.group_loan_id')

    @property
    def members(self):
        """Return parsed members data"""
        import json
        if self.members_json:
            try:
                return json.loads(self.members_json)
            except:
                return []
        return []

    def to_dict(self, include_payments=False, include_documents=False):
        data = {
            'id': self.id,
            'group_name': self.group_name,
            'member_count': self.member_count,
            'principal': float(self.principal) if self.principal else 0,
            'interest_rate': float(self.interest_rate) if self.interest_rate else 0,
            'interest_amount': float(self.interest_amount) if self.interest_amount else 0,
            'total_amount': float(self.total_amount),
            'amount_per_period': float(self.amount_per_period),
            'total_periods': self.total_periods,
            'period_type': self.period_type or 'monthly',
            'periods_paid': self.periods_paid,
            'periods_left': self.total_periods - self.periods_paid,
            'amount_paid': float(self.amount_paid),
            'balance': float(self.balance),
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_payments:
            data['payments'] = [p.to_dict() for p in self.payments.order_by(GroupLoanPayment.payment_date.desc())]
        if include_documents:
            data['documents'] = [d.to_dict() for d in self.documents.filter_by(is_deleted=False)]
        return data


class GroupLoanPayment(db.Model):
    """Group loan payments"""
    __tablename__ = 'group_loan_payments'

    id = db.Column(db.Integer, primary_key=True)
    group_loan_id = db.Column(db.Integer, db.ForeignKey('group_loans.id'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    periods_covered = db.Column(db.Integer, default=1)
    balance_after = db.Column(db.Numeric(12, 2), nullable=False)
    notes = db.Column(db.String(200), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)

    def to_dict(self):
        return {
            'id': self.id,
            'group_loan_id': self.group_loan_id,
            'group_name': self.group_loan.group_name if self.group_loan else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'amount': float(self.amount),
            'periods_covered': self.periods_covered,
            'balance_after': float(self.balance_after),
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class LoanDocument(db.Model):
    """Loan security documents/agreements"""
    __tablename__ = 'loan_documents'

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loans.id'), nullable=True)
    group_loan_id = db.Column(db.Integer, db.ForeignKey('group_loans.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(50), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'file_type': self.file_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
