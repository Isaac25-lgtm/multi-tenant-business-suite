from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.modules.finance import (
    allocate_loan_payment,
    calculate_reducing_balance_schedule,
    parse_individual_loan_form,
)


def test_reducing_balance_schedule_clears_principal():
    schedule = calculate_reducing_balance_schedule(
        Decimal('1500000'),
        Decimal('15'),
        3,
        date(2026, 6, 17),
    )

    assert len(schedule) == 3
    assert schedule[0]['interest'] == Decimal('225000')
    assert sum(row['principal'] for row in schedule) == Decimal('1500000')
    assert schedule[-1]['balance_after'] == Decimal('0')
    assert sum(row['payment'] for row in schedule) == (
        Decimal('1500000') + sum(row['interest'] for row in schedule)
    )


def test_parse_reducing_balance_form_sets_equal_payment_terms():
    loan_data = parse_individual_loan_form({
        'client_id': '1',
        'principal': '1500000',
        'interest_mode': 'reducing_balance_equal',
        'interest_rate': '15',
        'duration_weeks': '3',
        'duration_type': 'months',
        'issue_date': '2026-06-17',
    })

    assert loan_data['interest_mode'] == 'reducing_balance_equal'
    assert loan_data['monthly_interest_amount'] > 0
    assert loan_data['interest_amount'] > 0
    assert loan_data['total_amount'] == loan_data['principal'] + loan_data['interest_amount']
    assert loan_data['due_date'] == date(2026, 9, 17)


def test_reducing_balance_payment_allocation_follows_schedule():
    schedule = calculate_reducing_balance_schedule(
        Decimal('1500000'),
        Decimal('15'),
        3,
        date(2026, 6, 17),
    )
    loan = SimpleNamespace(
        principal=Decimal('1500000'),
        interest_rate=Decimal('15'),
        interest_mode='reducing_balance_equal',
        duration_weeks=3,
        issue_date=date(2026, 6, 17),
        amount_paid=Decimal('0'),
        principal_paid=Decimal('0'),
        interest_paid=Decimal('0'),
    )

    principal_amount, interest_amount = allocate_loan_payment(loan, schedule[0]['payment'])

    assert interest_amount == schedule[0]['interest']
    assert principal_amount == schedule[0]['principal']
    assert loan.amount_paid == schedule[0]['payment']
    assert loan.interest_paid == schedule[0]['interest']
    assert loan.principal_paid == schedule[0]['principal']
