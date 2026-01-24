from app.extensions import db
from datetime import datetime


class LoanClient(db.Model):
    """Loan clients (borrowers)"""
    __tablename__ = 'loan_clients'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    nin = db.Column(db.String(20), nullable=True)  # National ID Number
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    creator = db.relationship('User', foreign_keys=[created_by])
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
    interest_rate = db.Column(db.Numeric(5, 2), nullable=False)  # Percentage
    interest_amount = db.Column(db.Numeric(12, 2), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    amount_paid = db.Column(db.Numeric(12, 2), default=0)
    balance = db.Column(db.Numeric(12, 2), nullable=False)
    duration_weeks = db.Column(db.Integer, nullable=False)
    issue_date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum('active', 'overdue', 'due_soon', 'paid', 'renewed', name='loan_status'), default='active')
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    creator = db.relationship('User', foreign_keys=[created_by])
    payments = db.relationship('LoanPayment', backref='loan', lazy='dynamic')
    
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
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by_name': self.creator.name if self.creator else None
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    creator = db.relationship('User', foreign_keys=[created_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'loan_id': self.loan_id,
            'client_name': self.loan.client.name if self.loan and self.loan.client else None,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'amount': float(self.amount),
            'balance_after': float(self.balance_after),
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by_name': self.creator.name if self.creator else None
        }


class GroupLoan(db.Model):
    """Group loans"""
    __tablename__ = 'group_loans'
    
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False)
    member_count = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)
    amount_per_period = db.Column(db.Numeric(12, 2), nullable=False)
    total_periods = db.Column(db.Integer, nullable=False)
    periods_paid = db.Column(db.Integer, default=0)
    amount_paid = db.Column(db.Numeric(12, 2), default=0)
    balance = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.Enum('active', 'overdue', 'paid', name='group_loan_status'), default='active')
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    creator = db.relationship('User', foreign_keys=[created_by])
    payments = db.relationship('GroupLoanPayment', backref='group_loan', lazy='dynamic')
    
    def to_dict(self, include_payments=False):
        data = {
            'id': self.id,
            'group_name': self.group_name,
            'member_count': self.member_count,
            'total_amount': float(self.total_amount),
            'amount_per_period': float(self.amount_per_period),
            'total_periods': self.total_periods,
            'periods_paid': self.periods_paid,
            'periods_left': self.total_periods - self.periods_paid,
            'amount_paid': float(self.amount_paid),
            'balance': float(self.balance),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by_name': self.creator.name if self.creator else None
        }
        if include_payments:
            data['payments'] = [p.to_dict() for p in self.payments.order_by(GroupLoanPayment.payment_date.desc())]
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    creator = db.relationship('User', foreign_keys=[created_by])
    
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
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by_name': self.creator.name if self.creator else None
        }
