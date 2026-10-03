"""Monthly-accrual loan rules: timing, settlement cutoff, idempotency, allocation."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from flask import Flask

from app.models.finance import Loan
from app.services.loan_accounting import (
    allocate_loan_payment,
    anniversaries_reached,
    chargeable_months,
    refresh_loan_state,
    reverse_loan_payment_allocation,
)

D = Decimal
ISSUE = date(2026, 1, 10)


def make_loan(**overrides):
    values = dict(
        principal=D('1000000'), interest_rate=D('10'), interest_mode='monthly_accrual',
        monthly_interest_amount=D('100000'), interest_amount=D('0'), total_amount=D('1000000'),
        amount_paid=D('0'), principal_paid=D('0'), interest_paid=D('0'), principal_rolled=D('0'),
        balance=D('1000000'), duration_weeks=1, duration_type='months',
        issue_date=ISSUE, due_date=date(2026, 2, 10), status='active', settled_on=None,
    )
    values.update(overrides)
    return Loan(**values)


@pytest.fixture
def advance_app():
    app = Flask(__name__)
    app.config['MONTHLY_ACCRUAL_TIMING'] = 'advance'
    with app.app_context():
        yield app


# --- timing rules -----------------------------------------------------------

@pytest.mark.parametrize('as_of, expected', [
    (date(2026, 1, 9), 0),    # before issue
    (date(2026, 1, 10), 0),   # issue date: nothing yet
    (date(2026, 2, 9), 0),
    (date(2026, 2, 10), 1),   # first anniversary
    (date(2026, 2, 11), 1),
    (date(2026, 3, 10), 2),
    (date(2026, 4, 10), 3),   # "three months unpaid -> x3"
])
def test_arrears_timing(as_of, expected):
    assert chargeable_months(ISSUE, as_of, timing='arrears') == expected


@pytest.mark.parametrize('as_of, expected', [
    (date(2026, 1, 9), 0),    # before issue
    (date(2026, 1, 10), 1),   # first month charged on the issue date
    (date(2026, 2, 9), 1),
    (date(2026, 2, 10), 1),   # repaying on the due date costs one month
    (date(2026, 2, 11), 2),   # day after the anniversary
    (date(2026, 3, 11), 3),
    (date(2026, 4, 10), 3),   # three months -> x3, not x4
])
def test_advance_timing(as_of, expected):
    assert chargeable_months(ISSUE, as_of, timing='advance') == expected


def test_month_end_anniversaries_anchor_on_issue_date():
    issue = date(2026, 1, 31)
    assert anniversaries_reached(issue, date(2026, 2, 27)) == 0
    assert anniversaries_reached(issue, date(2026, 2, 28)) == 1   # 31 Jan + 1 month
    assert anniversaries_reached(issue, date(2026, 3, 30)) == 1
    assert anniversaries_reached(issue, date(2026, 3, 31)) == 2   # back to the 31st, not the 28th
    leap = date(2028, 1, 31)
    assert anniversaries_reached(leap, date(2028, 2, 29)) == 1


# --- refresh behaviour --------------------------------------------------------

def test_three_unpaid_months_accumulate_three_charges():
    loan = make_loan()
    refresh_loan_state(loan, date(2026, 4, 10))
    assert loan.interest_amount == D('300000')
    assert loan.total_amount == D('1300000')
    assert loan.balance == D('1300000')
    assert loan.status == 'overdue'


def test_advance_mode_charges_first_month_on_issue(advance_app):
    loan = make_loan()
    refresh_loan_state(loan, ISSUE)
    assert loan.interest_amount == D('100000')
    assert loan.balance == D('1100000')


def test_refresh_is_idempotent():
    loan = make_loan()
    as_of = date(2026, 3, 15)
    refresh_loan_state(loan, as_of)
    first = (loan.interest_amount, loan.total_amount, loan.balance, loan.status)
    for _ in range(10):
        assert refresh_loan_state(loan, as_of) is False
    assert (loan.interest_amount, loan.total_amount, loan.balance, loan.status) == first


def test_settled_loan_never_reopens():
    """Regression: a fully paid loan used to start owing again next month."""
    loan = make_loan()
    paid_on = date(2026, 2, 10)
    refresh_loan_state(loan, paid_on)
    allocate_loan_payment(loan, loan.balance)
    refresh_loan_state(loan, paid_on)
    assert loan.balance == 0
    assert loan.status == 'paid'
    assert loan.settled_on == paid_on

    for later in (date(2026, 3, 10), date(2026, 6, 10), date(2027, 1, 10)):
        refresh_loan_state(loan, later)
        assert loan.balance == 0
        assert loan.status == 'paid'


def test_reversal_reopens_accrual():
    loan = make_loan()
    paid_on = date(2026, 2, 10)
    refresh_loan_state(loan, paid_on)
    principal, interest = allocate_loan_payment(loan, loan.balance)
    refresh_loan_state(loan, paid_on)
    payment = SimpleNamespace(principal_amount=principal, interest_amount=interest)

    reverse_loan_payment_allocation(loan, payment)
    refresh_loan_state(loan, date(2026, 3, 10))
    assert loan.settled_on is None
    assert loan.balance == D('1200000')
    assert loan.status == 'overdue'


# --- payment allocation -------------------------------------------------------

def test_payment_goes_to_interest_first():
    loan = make_loan()
    refresh_loan_state(loan, date(2026, 4, 10))  # 300,000 interest charged
    principal, interest = allocate_loan_payment(loan, D('250000'))
    assert (principal, interest) == (D('0'), D('250000'))
    refresh_loan_state(loan, date(2026, 4, 10))
    assert loan.balance == D('1050000')


def test_payment_crosses_from_interest_into_principal():
    loan = make_loan()
    refresh_loan_state(loan, date(2026, 4, 10))
    allocate_loan_payment(loan, D('250000'))
    principal, interest = allocate_loan_payment(loan, D('200000'))
    assert (principal, interest) == (D('150000'), D('50000'))
    refresh_loan_state(loan, date(2026, 4, 10))
    assert loan.outstanding_principal == D('850000')
    assert loan.balance == D('850000')


def test_flat_rate_never_grows():
    loan = make_loan(interest_mode='flat_rate', monthly_interest_amount=None,
                     interest_amount=D('200000'), total_amount=D('1200000'), balance=D('1200000'))
    for as_of in (ISSUE, date(2026, 6, 10), date(2027, 6, 10)):
        refresh_loan_state(loan, as_of)
        assert loan.interest_amount == D('200000')
        assert loan.total_amount == D('1200000')
