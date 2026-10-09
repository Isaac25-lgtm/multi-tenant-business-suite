"""Convert open flat-rate loans to monthly interest.

Business rule (confirmed by the client): the rate entered on a loan is a
monthly rate and every loan accumulates. Loans that still owe money and were
stored as "flat rate" become monthly-interest loans at the same rate, and
their payments are re-allocated in date order (interest first). Paid and
renewed loans are left exactly as they are.

`convert_open_flat_loans()` changes the loans in the current database session
and returns a before/after row per loan. The caller decides: commit to apply,
or roll back for a preview.
"""
from decimal import Decimal

from app.extensions import db
from app.models.finance import Loan
from app.services.loan_accounting import refresh_loan_state, replay_loan_payments, round_money


def open_flat_loans_query():
    return Loan.query.filter(
        Loan.is_deleted == False,  # noqa: E712
        Loan.status.in_(['active', 'overdue']),
        db.or_(Loan.interest_mode.is_(None), Loan.interest_mode == 'flat_rate'),
    )


def count_open_flat_loans():
    return open_flat_loans_query().filter(Loan.balance > 0).count()


def convert_open_flat_loans():
    """Returns (rows, skipped). Nothing is committed here."""
    rows, skipped = [], []
    for loan in open_flat_loans_query().order_by(Loan.id).all():
        refresh_loan_state(loan)
        if (loan.balance or 0) <= 0:
            continue
        rate = Decimal(str(loan.interest_rate or 0))
        client_name = loan.client.name if loan.client else ''
        if rate <= 0:
            skipped.append({'loan_id': loan.id, 'client': client_name, 'reason': 'no interest rate recorded'})
            continue
        before = {'balance': float(loan.balance or 0), 'interest': float(loan.interest_amount or 0),
                  'principal_paid': float(loan.principal_paid or 0)}
        loan.interest_mode = 'monthly_accrual'
        loan.monthly_interest_amount = round_money(Decimal(str(loan.principal)) * rate / Decimal('100'))
        replay_loan_payments(loan)
        rows.append({
            'loan_id': loan.id,
            'client': client_name,
            'principal': float(loan.principal or 0),
            'rate_per_month': float(rate),
            'issue_date': loan.issue_date.isoformat() if loan.issue_date else '',
            'interest_before': before['interest'],
            'interest_after': float(loan.interest_amount or 0),
            'interest_paid_after': float(loan.interest_paid or 0),
            'principal_paid_before': before['principal_paid'],
            'principal_paid_after': float(loan.principal_paid or 0),
            'balance_before': before['balance'],
            'balance_after': float(loan.balance or 0),
            'status_after': loan.status,
        })
    return rows, skipped
