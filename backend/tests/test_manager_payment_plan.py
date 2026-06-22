from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.utils import pdf_generator
from app.utils.payment_plan import calculate_manager_payment_plan


def build_plan(**overrides):
    values = {
        'plan_amount': Decimal('1000000'),
        'deposit': Decimal('100000'),
        'interest_method': 'reducing_balance',
        'rate_percent': Decimal('31'),
        'rate_basis': 'annum',
        'frequency': 'monthly',
        'installments': 3,
        'first_due_date': date(2026, 7, 22),
    }
    values.update(overrides)
    return calculate_manager_payment_plan(**values)


def test_reducing_plan_uses_explicit_annual_basis_and_clears_balance():
    plan = build_plan()

    assert plan['periodic_rate'] == Decimal('0.31') / Decimal('12')
    assert plan['financed_amount'] == Decimal('900000')
    assert sum(row['principal'] for row in plan['schedule']) == Decimal('900000')
    assert plan['schedule'][-1]['balance_after'] == Decimal('0')
    assert plan['total_with_deposit'] == plan['deposit'] + plan['scheduled_payments']


def test_same_numeric_rate_per_month_is_not_treated_as_per_annum():
    annual_plan = build_plan(rate_basis='annum')
    monthly_plan = build_plan(rate_basis='month')

    assert monthly_plan['periodic_rate'] == Decimal('0.31')
    assert monthly_plan['total_interest'] > annual_plan['total_interest']


def test_flat_rate_respects_frequency_and_selected_basis():
    plan = build_plan(
        deposit=Decimal('0'),
        interest_method='flat_rate',
        rate_percent=Decimal('12'),
        rate_basis='annum',
        frequency='monthly',
        installments=6,
    )

    assert plan['total_interest'] == Decimal('60000')
    assert plan['scheduled_payments'] == Decimal('1060000')
    assert plan['schedule'][-1]['balance_after'] == Decimal('0')


def test_no_interest_ignores_rate_and_uses_selected_weekly_dates():
    plan = build_plan(
        interest_method='none',
        rate_percent=Decimal('31'),
        frequency='weekly',
        installments=2,
    )

    assert plan['rate_percent'] == Decimal('0')
    assert plan['total_interest'] == Decimal('0')
    assert plan['schedule'][1]['due_date'] == date(2026, 7, 29)


@pytest.mark.parametrize('deposit', [Decimal('-1'), Decimal('1000000')])
def test_invalid_deposit_is_rejected(deposit):
    with pytest.raises(ValueError, match='Deposit'):
        build_plan(deposit=deposit)


def test_full_manager_plan_renders_as_pdf(monkeypatch):
    settings = SimpleNamespace(
        logo_path=None,
        tagline='Finance',
        contact_phone='0700000000',
        headquarters='Kampala',
    )
    monkeypatch.setattr(pdf_generator, 'get_site_settings', lambda: settings)
    monkeypatch.setattr(
        pdf_generator,
        'get_company_display_name',
        lambda value=None: 'Denove APS',
    )
    loan = SimpleNamespace(
        id=7,
        client=SimpleNamespace(name='Test Client', phone='0700000000', nin='TEST-NIN'),
        interest_mode='flat_rate',
        due_date=date(2026, 6, 1),
        principal=Decimal('1000000'),
        interest_amount=Decimal('150000'),
        total_amount=Decimal('1150000'),
        amount_paid=Decimal('150000'),
        balance=Decimal('1000000'),
    )
    plan = build_plan(installments=6)
    plan.update({
        'title': 'Proposed Payment Plan',
        'manager_notes': 'Client requested a revised schedule.',
        'plan_terms': 'Payments are due on the dates shown.',
        'prepared_by': 'Manager',
        'unplanned_balance': Decimal('0'),
    })

    buffer = pdf_generator.generate_payment_plan_pdf(loan, [], plan)

    assert buffer.getvalue().startswith(b'%PDF-')
    assert len(buffer.getvalue()) > 4000
