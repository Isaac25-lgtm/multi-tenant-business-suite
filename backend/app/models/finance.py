import json
from decimal import Decimal

from app.extensions import db
from app.utils.pii import decrypt_value, encrypt_value
from app.utils.timezone import get_local_now


class LoanClient(db.Model):
    """Loan clients (borrowers)"""
    __tablename__ = 'loan_clients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    _nin_plaintext = db.Column('nin', db.String(255), nullable=True)
    nin_encrypted = db.Column(db.Text, nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    payer_status = db.Column(db.String(20), nullable=False, default='neutral')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_local_now)

    loans = db.relationship('Loan', backref='client', lazy='dynamic')

    @property
    def payer_status_label(self):
        return {
            'good': 'Good Payer',
            'bad': 'Poor Payer',
        }.get(self.payer_status or 'neutral', 'Unmarked')

    @property
    def nin(self):
        if self.nin_encrypted:
            return decrypt_value(self.nin_encrypted)
        return self._nin_plaintext

    @nin.setter
    def nin(self, value):
        normalized = str(value or '').strip()
        if not normalized:
            self.nin_encrypted = None
            self._nin_plaintext = None
            return
        self.nin_encrypted = encrypt_value(normalized)
        self._nin_plaintext = None

    def ensure_nin_encrypted(self):
        if self._nin_plaintext and not self.nin_encrypted:
            self.nin = self._nin_plaintext

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'nin': self.nin,
            'phone': self.phone,
            'address': self.address,
            'payer_status': self.payer_status or 'neutral',
            'payer_status_label': self.payer_status_label,
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
    interest_mode = db.Column(db.String(30), default='flat_rate')
    monthly_interest_amount = db.Column(db.Numeric(12, 2), nullable=True)
    interest_amount = db.Column(db.Numeric(12, 2), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(12, 2), default=0)
    balance = db.Column(db.Numeric(12, 2), nullable=False)
    duration_weeks = db.Column(db.Integer, nullable=False)
    duration_type = db.Column(db.String(10), default='weeks')  # 'weeks' or 'months'
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='active')
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)
    deleted_at = db.Column(db.DateTime, nullable=True)

    payments = db.relationship('LoanPayment', backref='loan', lazy='dynamic')
    documents = db.relationship('LoanDocument', backref='loan', lazy='dynamic',
                               primaryjoin='Loan.id==LoanDocument.loan_id')

    @property
    def outstanding_principal(self):
        principal = Decimal(str(self.principal or 0))
        amount_paid = Decimal(str(self.amount_paid or 0))
        balance = Decimal(str(self.balance or 0))
        remaining_principal = principal - amount_paid
        if remaining_principal < 0:
            remaining_principal = Decimal('0')
        if remaining_principal > balance:
            remaining_principal = balance
        return remaining_principal

    @property
    def outstanding_interest(self):
        balance = Decimal(str(self.balance or 0))
        remaining_interest = balance - self.outstanding_principal
        if remaining_interest < 0:
            return Decimal('0')
        return remaining_interest

    def to_dict(self, include_payments=False):
        data = {
            'id': self.id,
            'client_id': self.client_id,
            'client': self.client.to_dict() if self.client else None,
            'principal': float(self.principal),
            'interest_rate': float(self.interest_rate),
            'interest_mode': self.interest_mode or 'flat_rate',
            'monthly_interest_amount': float(self.monthly_interest_amount or 0),
            'interest_amount': float(self.interest_amount),
            'total_amount': float(self.total_amount),
            'amount_paid': float(self.amount_paid),
            'balance': float(self.balance),
            'outstanding_principal': float(self.outstanding_principal),
            'outstanding_interest': float(self.outstanding_interest),
            'duration_weeks': self.duration_weeks,
            'duration_type': self.duration_type or 'weeks',
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
    status = db.Column(db.String(20), default='active')
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)

    payments = db.relationship('GroupLoanPayment', backref='group_loan', lazy='dynamic')
    documents = db.relationship('LoanDocument', backref='group_loan', lazy='dynamic',
                               primaryjoin='GroupLoan.id==LoanDocument.group_loan_id')

    @property
    def outstanding_principal(self):
        principal = Decimal(str(self.principal or 0))
        amount_paid = Decimal(str(self.amount_paid or 0))
        balance = Decimal(str(self.balance or 0))
        remaining_principal = principal - amount_paid
        if remaining_principal < 0:
            remaining_principal = Decimal('0')
        if remaining_principal > balance:
            remaining_principal = balance
        return remaining_principal

    @property
    def outstanding_interest(self):
        balance = Decimal(str(self.balance or 0))
        remaining_interest = balance - self.outstanding_principal
        if remaining_interest < 0:
            return Decimal('0')
        return remaining_interest

    @property
    def members(self):
        """Return parsed members data"""
        if self.members_json:
            try:
                raw_members = json.loads(self.members_json)
                members = []
                for member in raw_members:
                    member_copy = dict(member)
                    encrypted_nin = member_copy.get('nin_encrypted')
                    if encrypted_nin:
                        member_copy['nin'] = decrypt_value(encrypted_nin)
                    else:
                        member_copy['nin'] = member_copy.get('nin')
                    members.append(member_copy)
                return members
            except (TypeError, ValueError, json.JSONDecodeError):
                return []
        return []

    def set_members(self, members):
        serialized_members = []
        for member in members or []:
            member_copy = dict(member)
            nin = str(member_copy.pop('nin', '') or '').strip()
            member_copy['nin_encrypted'] = encrypt_value(nin) if nin else None
            serialized_members.append(member_copy)
        self.members_json = json.dumps(serialized_members)

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
            'outstanding_principal': float(self.outstanding_principal),
            'outstanding_interest': float(self.outstanding_interest),
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
