"""Calculation helpers for manager-authored loan payment plans."""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP, localcontext

from dateutil.relativedelta import relativedelta


MONEY_QUANT = Decimal('1')
MAX_INSTALLMENTS = 120
INTEREST_METHODS = {'reducing_balance', 'flat_rate', 'none'}
RATE_BASES = {'month', 'annum'}
PAYMENT_FREQUENCIES = {'weekly', 'bi_weekly', 'monthly'}
PERIODS_PER_YEAR = {
    'weekly': Decimal('52'),
    'bi_weekly': Decimal('26'),
    'monthly': Decimal('12'),
}


def _money(value):
    return Decimal(str(value or 0)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _next_due_date(first_due_date, frequency, index):
    if frequency == 'monthly':
        return first_due_date + relativedelta(months=index)
    if frequency == 'bi_weekly':
        return first_due_date + timedelta(weeks=2 * index)
    return first_due_date + timedelta(weeks=index)


def _periodic_rate(rate_percent, rate_basis, frequency):
    """Convert the selected monthly/annual nominal rate into a schedule-period rate."""
    annual_rate = rate_percent if rate_basis == 'annum' else rate_percent * Decimal('12')
    return (annual_rate / Decimal('100')) / PERIODS_PER_YEAR[frequency]


def calculate_manager_payment_plan(
    plan_amount,
    deposit,
    interest_method,
    rate_percent,
    rate_basis,
    frequency,
    installments,
    first_due_date,
):
    """Return the exact schedule requested by a manager.

    The rate is deliberately paired with an explicit basis. A value of 31 with
    ``annum`` can therefore never be silently interpreted as 31% per month.
    """
    plan_amount = _money(plan_amount)
    deposit = _money(deposit)
    rate_percent = Decimal(str(rate_percent or 0))

    if plan_amount <= 0:
        raise ValueError('Amount to place on the plan must be greater than zero.')
    if deposit < 0 or deposit >= plan_amount:
        raise ValueError('Deposit must be zero or less than the amount placed on the plan.')
    if interest_method not in INTEREST_METHODS:
        raise ValueError('Select a valid interest method.')
    if rate_basis not in RATE_BASES:
        raise ValueError('Select whether the rate is per month or per annum.')
    if frequency not in PAYMENT_FREQUENCIES:
        raise ValueError('Select a valid payment frequency.')
    if not isinstance(installments, int) or not 1 <= installments <= MAX_INSTALLMENTS:
        raise ValueError(f'Installments must be between 1 and {MAX_INSTALLMENTS}.')
    if not first_due_date:
        raise ValueError('Select the first payment date.')
    if rate_percent < 0 or rate_percent > Decimal('100'):
        raise ValueError('Interest rate must be between 0 and 100 percent.')
    if interest_method != 'none' and rate_percent <= 0:
        raise ValueError('Enter an interest rate, or select No additional interest.')

    financed_amount = plan_amount - deposit
    periodic_rate = Decimal('0')
    if interest_method != 'none':
        periodic_rate = _periodic_rate(rate_percent, rate_basis, frequency)

    schedule = []
    remaining = financed_amount

    if interest_method == 'reducing_balance':
        with localcontext() as context:
            context.prec = 36
            if periodic_rate == 0:
                regular_payment = _money(financed_amount / installments)
            else:
                growth = (Decimal('1') + periodic_rate) ** installments
                regular_payment = _money(
                    financed_amount * periodic_rate * growth / (growth - Decimal('1'))
                )

        for index in range(installments):
            opening = remaining
            interest = _money(opening * periodic_rate)
            if index == installments - 1:
                principal = opening
                payment = principal + interest
            else:
                payment = regular_payment
                principal = payment - interest
                if principal <= 0:
                    raise ValueError('The selected installment terms do not reduce the balance.')
                principal = min(principal, opening)
                payment = principal + interest
            remaining = max(opening - principal, Decimal('0'))
            schedule.append({
                'period': index + 1,
                'due_date': _next_due_date(first_due_date, frequency, index),
                'opening_balance': opening,
                'payment': payment,
                'interest': interest,
                'principal': principal,
                'balance_after': remaining,
            })
    else:
        total_interest = Decimal('0')
        if interest_method == 'flat_rate':
            basis_periods = (
                PERIODS_PER_YEAR[frequency]
                if rate_basis == 'annum'
                else PERIODS_PER_YEAR[frequency] / Decimal('12')
            )
            duration_in_basis_units = Decimal(installments) / basis_periods
            total_interest = _money(
                financed_amount * (rate_percent / Decimal('100')) * duration_in_basis_units
            )

        regular_principal = _money(financed_amount / installments)
        regular_interest = _money(total_interest / installments)
        principal_left = financed_amount
        interest_left = total_interest
        for index in range(installments):
            opening = principal_left
            if index == installments - 1:
                principal = principal_left
                interest = interest_left
            else:
                principal = min(regular_principal, principal_left)
                interest = min(regular_interest, interest_left)
            payment = principal + interest
            principal_left = max(principal_left - principal, Decimal('0'))
            interest_left = max(interest_left - interest, Decimal('0'))
            schedule.append({
                'period': index + 1,
                'due_date': _next_due_date(first_due_date, frequency, index),
                'opening_balance': opening,
                'payment': payment,
                'interest': interest,
                'principal': principal,
                'balance_after': principal_left,
            })

    total_interest = sum((row['interest'] for row in schedule), Decimal('0'))
    scheduled_payments = sum((row['payment'] for row in schedule), Decimal('0'))
    return {
        'plan_amount': plan_amount,
        'deposit': deposit,
        'financed_amount': financed_amount,
        'interest_method': interest_method,
        'rate_percent': rate_percent if interest_method != 'none' else Decimal('0'),
        'rate_basis': rate_basis,
        'frequency': frequency,
        'installments': installments,
        'first_due_date': first_due_date,
        'periodic_rate': periodic_rate,
        'schedule': schedule,
        'total_interest': total_interest,
        'scheduled_payments': scheduled_payments,
        'total_with_deposit': deposit + scheduled_payments,
    }
