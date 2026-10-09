"""Authoritative loan calculations for individual and group loans.

Every balance shown on screen, in PDFs, or on the dashboard should come from
these functions so the same loan never shows two different numbers.

Interest modes
--------------
flat_rate
    Interest is charged once: principal x rate. It never grows.
monthly_accrual
    Interest is charged once per month on the principal still unpaid on the
    charge date (rate = monthly_interest_amount / original principal), so the
    charge falls when principal is repaid. Charges continue after the due date
    until the loan is settled, and stop on the settlement date, so a cleared
    loan never reopens. Charge dates follow MONTHLY_ACCRUAL_TIMING:
      * 'advance' (default, the business rule confirmed by the client): the
        first month is charged on the issue date and each later month the day
        *after* a monthly anniversary, so paying on the due date costs exactly
        the months already charged.
      * 'arrears': one charge on each monthly anniversary; nothing on issue.
reducing_balance_equal
    Equal monthly payments on a reducing principal (annuity schedule).

The refresh is deterministic: running it any number of times for the same
date gives the same result. Nothing is ever added to a balance incrementally.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from flask import current_app, has_app_context

from app.extensions import db
from app.models.finance import GroupLoan, Loan
from app.utils.timezone import get_local_today

MONEY_QUANT = Decimal('1')
ZERO = Decimal('0')
ACCRUAL_TIMINGS = ('arrears', 'advance')
DEFAULT_ACCRUAL_TIMING = 'advance'


def _d(value):
    """Coerce a stored value (Decimal, float, int, None) to Decimal."""
    return Decimal(str(value or 0))


def round_money(value):
    return Decimal(str(value or 0)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def get_accrual_timing():
    timing = DEFAULT_ACCRUAL_TIMING
    if has_app_context():
        timing = (current_app.config.get('MONTHLY_ACCRUAL_TIMING') or DEFAULT_ACCRUAL_TIMING).strip().lower()
    return timing if timing in ACCRUAL_TIMINGS else DEFAULT_ACCRUAL_TIMING


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def monthly_anniversary(issue_date, k):
    """The k-th monthly anniversary, always anchored on the issue date.

    Anchoring on the issue date (rather than chaining month to month) keeps
    month-end loans stable: 31 Jan -> 28 Feb -> 31 Mar, never 28 Mar.
    """
    return issue_date + relativedelta(months=k)


def anniversaries_reached(issue_date, as_of_date, inclusive=True):
    """Count monthly anniversaries (k >= 1) on or before `as_of_date`.

    With inclusive=False, only anniversaries strictly before `as_of_date` count.
    """
    if not issue_date or not as_of_date or as_of_date <= issue_date:
        return 0
    delta = relativedelta(as_of_date, issue_date)
    count = max((delta.years * 12) + delta.months - 1, 0)
    while True:
        anniversary = monthly_anniversary(issue_date, count + 1)
        if anniversary < as_of_date or (inclusive and anniversary == as_of_date):
            count += 1
        else:
            return count


def elapsed_full_months(issue_date, reference_date):
    """Completed monthly anniversaries between two dates (kept for callers)."""
    return anniversaries_reached(issue_date, reference_date, inclusive=True)


def chargeable_months(issue_date, as_of_date, timing=None):
    """Number of monthly interest charges due for a monthly-accrual loan."""
    if not issue_date or not as_of_date or as_of_date < issue_date:
        return 0
    timing = timing or get_accrual_timing()
    if timing == 'advance':
        return 1 + anniversaries_reached(issue_date, as_of_date, inclusive=False)
    return anniversaries_reached(issue_date, as_of_date, inclusive=True)


def monthly_charge_dates(issue_date, as_of_date, timing=None):
    """Every date on which a monthly interest charge falls, up to `as_of_date`."""
    if not issue_date or not as_of_date or as_of_date < issue_date:
        return []
    timing = timing or get_accrual_timing()
    dates = [issue_date] if timing == 'advance' else []
    offset = timedelta(days=1) if timing == 'advance' else timedelta(0)
    k = 1
    while True:
        charge_date = monthly_anniversary(issue_date, k) + offset
        if charge_date > as_of_date:
            return dates
        dates.append(charge_date)
        k += 1


def calculate_due_date(issue_date, duration_units, duration_type):
    if duration_type == 'months':
        return issue_date + relativedelta(months=duration_units)
    return issue_date + timedelta(weeks=duration_units)


# ---------------------------------------------------------------------------
# Reducing-balance schedule
# ---------------------------------------------------------------------------

def calculate_reducing_balance_schedule(principal, monthly_rate_percent, periods, issue_date=None):
    """Build an equal-payment reducing-balance monthly amortization schedule."""
    principal = round_money(principal)
    monthly_rate_percent = Decimal(str(monthly_rate_percent or 0))
    periods = int(periods or 0)

    if principal <= 0 or periods <= 0:
        return []

    monthly_rate = monthly_rate_percent / Decimal('100')
    if monthly_rate == 0:
        regular_payment = round_money(principal / Decimal(periods))
    else:
        discount = Decimal('1') - ((Decimal('1') + monthly_rate) ** -periods)
        regular_payment = round_money((principal * monthly_rate) / discount)

    rows = []
    remaining = principal
    for period in range(1, periods + 1):
        interest = round_money(remaining * monthly_rate)
        principal_component = regular_payment - interest

        if period == periods or principal_component > remaining:
            principal_component = remaining
            payment = principal_component + interest
        else:
            payment = regular_payment

        remaining -= principal_component
        if remaining < 0:
            remaining = ZERO

        due_date = issue_date + relativedelta(months=period) if issue_date else None
        rows.append({
            'period': period,
            'due_date': due_date,
            'payment': round_money(payment),
            'interest': round_money(interest),
            'principal': round_money(principal_component),
            'balance_after': round_money(remaining),
        })

    return rows


def get_loan_payment_schedule(loan):
    if (loan.interest_mode or 'flat_rate') != 'reducing_balance_equal':
        return []
    return calculate_reducing_balance_schedule(
        loan.principal or 0,
        loan.interest_rate or 0,
        loan.duration_weeks or 0,
        loan.issue_date,
    )


# ---------------------------------------------------------------------------
# Individual loans
# ---------------------------------------------------------------------------

def principal_reductions(loan):
    """(date, amount) for everything that has reduced a loan's principal.

    Principal repaid through payments and principal written off. Tests and
    replays may supply `loan._principal_events` to avoid touching the database.
    """
    supplied = getattr(loan, '_principal_events', None)
    if supplied is not None:
        return supplied
    loan_id = getattr(loan, 'id', None)
    if not loan_id or not has_app_context():
        return []
    from app.models.finance import LoanAdjustment, LoanPayment

    events = [(row.payment_date, _d(row.principal_amount)) for row in LoanPayment.query.filter(
        LoanPayment.loan_id == loan_id,
        LoanPayment.is_deleted == False,  # noqa: E712
        LoanPayment.principal_amount > 0,
    ).all()]
    events += [(row.effective_date, _d(row.amount)) for row in LoanAdjustment.query.filter(
        LoanAdjustment.loan_id == loan_id,
        LoanAdjustment.adjustment_type == 'principal_write_off',
        LoanAdjustment.is_reversed == False,  # noqa: E712
    ).all()]
    return events


def monthly_rate(loan):
    """Monthly interest as a fraction of principal (e.g. 0.15 for 15%)."""
    principal = _d(loan.principal)
    if principal <= 0:
        return ZERO
    return _d(loan.monthly_interest_amount) / principal


def current_monthly_interest(loan):
    """The next monthly charge at today's unpaid principal."""
    return round_money(monthly_rate(loan) * _d(loan.outstanding_principal))


def accrued_interest(loan, as_of_date):
    """Interest charged on a loan up to `as_of_date` (before any payments)."""
    interest_mode = loan.interest_mode or 'flat_rate'

    if interest_mode == 'monthly_accrual':
        accrual_date = as_of_date
        settled_on = getattr(loan, 'settled_on', None)
        if settled_on and settled_on < accrual_date:
            accrual_date = settled_on
        principal = _d(loan.principal)
        rate = monthly_rate(loan)
        reductions = principal_reductions(loan)
        total = ZERO
        for charge_date in monthly_charge_dates(loan.issue_date, accrual_date):
            # Principal repaid before the charge date lowers that month's interest.
            repaid = sum((amount for when, amount in reductions if when < charge_date), ZERO)
            total += round_money(rate * max(principal - repaid, ZERO))
        return total

    if interest_mode == 'reducing_balance_equal':
        return sum((row['interest'] for row in get_loan_payment_schedule(loan)), ZERO)

    return _d(loan.interest_amount)


def refresh_loan_state(loan, as_of_date=None):
    """Recompute a loan's totals, balance and status as of a date.

    Idempotent: the result depends only on the loan's terms, dates and the
    amounts already paid. Returns True when any stored value changed.
    """
    as_of_date = as_of_date or get_local_today()
    changed = False

    # A settled loan is frozen: it was cleared under the rules of its time, so
    # later rule or setting changes never reopen it. Reversing a payment or
    # adding a charge clears settled_on first, which unfreezes it.
    if (getattr(loan, 'settled_on', None) is not None
            and (loan.status or '') in ('paid', 'renewed')
            and _d(loan.balance) <= 0):
        return False

    principal = _d(loan.principal)
    principal_paid = _d(loan.principal_paid)
    interest_paid = _d(loan.interest_paid)
    principal_rolled = _d(loan.principal_rolled)
    interest_waived = _d(getattr(loan, 'interest_waived', 0))
    written_off = _d(getattr(loan, 'principal_written_off', 0))
    charges = _d(getattr(loan, 'charges_added', 0))
    interest_mode = loan.interest_mode or 'flat_rate'

    interest_amount = accrued_interest(loan, as_of_date)
    if interest_mode == 'reducing_balance_equal':
        total_amount = sum((row['payment'] for row in get_loan_payment_schedule(loan)), ZERO) + charges
    else:
        # "Current due": principal plus everything charged so far, before payments.
        total_amount = principal + interest_amount + charges

    principal_due = max(principal - principal_paid - principal_rolled - written_off, ZERO)
    interest_due = max(interest_amount + charges - interest_paid - interest_waived, ZERO)
    balance = max(principal_due + interest_due, ZERO)

    if (loan.status or '').lower() == 'renewed' and balance <= 0:
        status = 'renewed'
    elif balance <= 0:
        status = 'paid'
    elif loan.due_date and loan.due_date < as_of_date:
        status = 'overdue'
    else:
        status = 'active'

    # Record when the loan was cleared so monthly accrual stops there.
    if balance <= 0 and getattr(loan, 'settled_on', None) is None and hasattr(loan, 'settled_on'):
        loan.settled_on = as_of_date
        changed = True

    if _d(loan.interest_amount) != interest_amount:
        loan.interest_amount = interest_amount
        changed = True
    if _d(loan.total_amount) != total_amount:
        loan.total_amount = total_amount
        changed = True
    amount_paid = principal_paid + interest_paid
    if _d(loan.amount_paid) != amount_paid:
        loan.amount_paid = amount_paid
        changed = True
    if _d(loan.balance) != balance:
        loan.balance = balance
        changed = True
    if (loan.status or 'active') != status:
        loan.status = status
        changed = True
    return changed


def allocate_loan_payment(loan, amount):
    """Apply a payment interest-first, then principal, and return the allocation."""
    amount = _d(amount)

    if (loan.interest_mode or 'flat_rate') == 'reducing_balance_equal':
        schedule = get_loan_payment_schedule(loan)
        current_paid = _d(loan.amount_paid)
        target_paid = current_paid + amount
        scheduled_total = sum((row['payment'] for row in schedule), ZERO)
        if target_paid > scheduled_total:
            target_paid = scheduled_total

        remaining_paid = target_paid
        target_interest = ZERO
        target_principal = ZERO
        for row in schedule:
            row_payment = _d(row['payment'])
            if remaining_paid <= 0:
                break

            applied = min(remaining_paid, row_payment)
            row_interest = _d(row['interest'])
            row_principal = _d(row['principal'])
            interest_part = min(applied, row_interest)
            principal_part = applied - interest_part
            if principal_part > row_principal:
                principal_part = row_principal

            target_interest += interest_part
            target_principal += principal_part
            remaining_paid -= applied

        current_interest_paid = _d(loan.interest_paid)
        current_principal_paid = _d(loan.principal_paid)
        interest_amount = max(target_interest - current_interest_paid, ZERO)
        principal_amount = max(target_principal - current_principal_paid, ZERO)

        loan.interest_paid = current_interest_paid + interest_amount
        loan.principal_paid = current_principal_paid + principal_amount
        loan.amount_paid = current_paid + interest_amount + principal_amount

        return principal_amount, interest_amount

    interest_due = _d(loan.outstanding_interest)
    principal_due = _d(loan.outstanding_principal)

    interest_amount = min(amount, interest_due)
    principal_amount = amount - interest_amount
    if principal_amount > principal_due:
        principal_amount = principal_due

    loan.interest_paid = _d(loan.interest_paid) + interest_amount
    loan.principal_paid = _d(loan.principal_paid) + principal_amount
    loan.amount_paid = _d(loan.amount_paid) + interest_amount + principal_amount

    return principal_amount, interest_amount


def preview_loan_payment(loan, amount, payment_date):
    """How a payment would be split, computed on a detached copy (nothing is saved).

    Uses exactly the same refresh + allocation steps as recording a payment.
    """
    copy = Loan(**{column.name: getattr(loan, column.name) for column in Loan.__table__.columns})
    refresh_loan_state(copy, payment_date)
    balance_before = _d(copy.balance)
    amount = min(_d(amount), balance_before)
    principal, interest = allocate_loan_payment(copy, amount)
    refresh_loan_state(copy, payment_date)
    return {
        'amount': amount,
        'interest': interest,
        'principal': principal,
        'balance_before': balance_before,
        'balance_after': _d(copy.balance),
        'settles_loan': _d(copy.balance) <= 0,
    }


def replay_loan_payments(loan, as_of_date=None):
    """Re-allocate every payment in date order under the current rules.

    Needed whenever history changes out of order (a backdated payment, a
    reversal, or a loan converted to monthly interest), because how a payment
    splits into interest and principal depends on what was owed on its date.
    Adjustments are applied from their effective dates. Deterministic:
    running it twice gives the same result.
    """
    from app.models.finance import LoanAdjustment, LoanPayment

    if (loan.status or '') == 'renewed':
        return False
    payments = LoanPayment.query.filter(
        LoanPayment.loan_id == loan.id,
        LoanPayment.is_deleted == False,  # noqa: E712
    ).order_by(LoanPayment.payment_date.asc(), LoanPayment.id.asc()).all()
    adjustments = LoanAdjustment.query.filter(
        LoanAdjustment.loan_id == loan.id,
        LoanAdjustment.is_reversed == False,  # noqa: E712
    ).all()

    def apply_adjustments_as_of(when):
        totals = {field: ZERO for field in set(ADJUSTMENT_FIELDS.values())}
        for adjustment in adjustments:
            if when is None or adjustment.effective_date <= when:
                totals[ADJUSTMENT_FIELDS[adjustment.adjustment_type]] += _d(adjustment.amount)
        for field, total in totals.items():
            setattr(loan, field, total)

    loan.principal_paid = ZERO
    loan.interest_paid = ZERO
    loan.amount_paid = ZERO
    loan.settled_on = None
    if (loan.status or '') == 'paid':
        loan.status = 'active'
    events = [(adjustment.effective_date, _d(adjustment.amount)) for adjustment in adjustments
              if adjustment.adjustment_type == 'principal_write_off']
    loan._principal_events = events
    try:
        for payment in payments:
            apply_adjustments_as_of(payment.payment_date)
            refresh_loan_state(loan, payment.payment_date)
            usable = min(_d(payment.amount), _d(loan.balance))
            principal, interest = allocate_loan_payment(loan, usable)
            payment.principal_amount = principal
            payment.interest_amount = interest
            if principal > 0:
                events.append((payment.payment_date, principal))
            refresh_loan_state(loan, payment.payment_date)
            payment.balance_after = loan.balance
            if _d(loan.balance) > 0:
                loan.settled_on = None
        apply_adjustments_as_of(None)
        if loan.settled_on:
            # Re-check the settlement with every adjustment applied: it only
            # stands if the balance is still zero on that date.
            settled = loan.settled_on
            loan.settled_on = None
            refresh_loan_state(loan, settled)
        refresh_loan_state(loan, as_of_date)
    finally:
        del loan._principal_events
    return True


def reverse_loan_payment_allocation(loan, payment):
    """Undo a payment's principal/interest allocation and reopen accrual."""
    loan.principal_paid = max(_d(loan.principal_paid) - _d(payment.principal_amount), ZERO)
    loan.interest_paid = max(_d(loan.interest_paid) - _d(payment.interest_amount), ZERO)
    loan.amount_paid = _d(loan.principal_paid) + _d(loan.interest_paid)
    loan.settled_on = None
    if (loan.status or '') == 'paid':
        loan.status = 'active'


# ---------------------------------------------------------------------------
# Adjustments (discounts, waivers, write-offs, charges)
# ---------------------------------------------------------------------------

ADJUSTMENT_FIELDS = {
    'interest_discount': 'interest_waived',
    'interest_waiver': 'interest_waived',
    'principal_write_off': 'principal_written_off',
    'charge': 'charges_added',
}


def adjustment_limit(target, adjustment_type):
    """Largest amount an adjustment of this type may have right now (None = no cap)."""
    if adjustment_type in ('interest_discount', 'interest_waiver'):
        return _d(target.outstanding_interest)
    if adjustment_type == 'principal_write_off':
        return _d(target.outstanding_principal)
    return None


def apply_adjustment(target, adjustment, reverse=False):
    """Add (or remove, when reversing) an adjustment from the running totals."""
    field = ADJUSTMENT_FIELDS[adjustment.adjustment_type]
    current = _d(getattr(target, field, 0))
    amount = _d(adjustment.amount)
    setattr(target, field, max(current - amount, ZERO) if reverse else current + amount)
    if hasattr(target, 'settled_on') and (reverse or adjustment.adjustment_type == 'charge'):
        target.settled_on = None
        if (target.status or '') == 'paid':
            target.status = 'active'


def refresh_active_loans(as_of_date=None):
    """Refresh every open individual loan. Safe to run repeatedly."""
    changed = False
    loans = Loan.query.filter(
        Loan.is_deleted == False,  # noqa: E712
        Loan.status != 'renewed',
        Loan.settled_on.is_(None),
    ).all()
    events = _principal_events_by_loan([loan.id for loan in loans])
    for loan in loans:
        loan._principal_events = events.get(loan.id, [])
        try:
            changed = refresh_loan_state(loan, as_of_date) or changed
        finally:
            del loan._principal_events
    if changed:
        db.session.commit()
    return changed


def _principal_events_by_loan(loan_ids):
    from app.models.finance import LoanAdjustment, LoanPayment

    events = {}
    if not loan_ids:
        return events
    for loan_id, when, amount in db.session.query(
        LoanPayment.loan_id, LoanPayment.payment_date, LoanPayment.principal_amount
    ).filter(
        LoanPayment.loan_id.in_(loan_ids),
        LoanPayment.is_deleted == False,  # noqa: E712
        LoanPayment.principal_amount > 0,
    ).all():
        events.setdefault(loan_id, []).append((when, _d(amount)))
    for loan_id, when, amount in db.session.query(
        LoanAdjustment.loan_id, LoanAdjustment.effective_date, LoanAdjustment.amount
    ).filter(
        LoanAdjustment.loan_id.in_(loan_ids),
        LoanAdjustment.adjustment_type == 'principal_write_off',
        LoanAdjustment.is_reversed == False,  # noqa: E712
    ).all():
        events.setdefault(loan_id, []).append((when, _d(amount)))
    return events


# ---------------------------------------------------------------------------
# Group loans
# ---------------------------------------------------------------------------

def refresh_group_loan_state(group, as_of_date=None):
    """Recompute a group loan's balance and status. Returns True on change."""
    as_of_date = as_of_date or get_local_today()
    changed = False

    balance = max(
        _d(group.total_amount) + _d(getattr(group, 'charges_added', 0))
        - _d(group.amount_paid) - _d(getattr(group, 'interest_waived', 0))
        - _d(getattr(group, 'principal_written_off', 0)),
        ZERO,
    )

    # Periods paid follow the money actually paid, never a separate entry.
    per_period = _d(group.amount_per_period)
    total_periods = int(group.total_periods or 0)
    if balance <= 0:
        periods_paid = total_periods
    elif per_period > 0:
        # 1 UGX tolerance absorbs rounding in non-integer per-period amounts.
        periods_paid = min(int((_d(group.amount_paid) + 1) // per_period), total_periods)
    else:
        periods_paid = int(group.periods_paid or 0)
    if int(group.periods_paid or 0) != periods_paid:
        group.periods_paid = periods_paid
        changed = True

    if balance <= 0:
        status = 'paid'
    elif group.due_date and group.due_date < as_of_date:
        status = 'overdue'
    else:
        status = 'active'

    if _d(group.balance) != balance:
        group.balance = balance
        changed = True
    if (group.status or 'active') != status:
        group.status = status
        changed = True
    return changed


def refresh_open_group_loans(as_of_date=None):
    """Refresh every non-deleted group loan's balance and status."""
    changed = False
    groups = GroupLoan.query.filter(GroupLoan.is_deleted == False).all()  # noqa: E712
    for group in groups:
        changed = refresh_group_loan_state(group, as_of_date) or changed
    if changed:
        db.session.commit()
    return changed


# ---------------------------------------------------------------------------
# Portfolio totals
# ---------------------------------------------------------------------------

def _open_loans():
    return Loan.query.filter(
        Loan.is_deleted == False,  # noqa: E712
        Loan.status != 'renewed',
        Loan.balance > 0,
    ).all()


def _open_group_loans():
    return GroupLoan.query.filter(
        GroupLoan.is_deleted == False,  # noqa: E712
        GroupLoan.balance > 0,
    ).all()


def summarize_portfolio(loans=None, groups=None):
    """Outstanding principal, interest and balance split by portfolio.

    All values are Decimal. Pass explicit lists to summarise a filtered set.
    """
    loans = _open_loans() if loans is None else loans
    groups = _open_group_loans() if groups is None else groups

    individual_principal = sum((_d(loan.outstanding_principal) for loan in loans), ZERO)
    individual_interest = sum((_d(loan.outstanding_interest) for loan in loans), ZERO)
    group_principal = sum((_d(group.outstanding_principal) for group in groups), ZERO)
    group_interest = sum((_d(group.outstanding_interest) for group in groups), ZERO)

    return {
        'individual_principal': individual_principal,
        'individual_interest': individual_interest,
        'individual_balance': individual_principal + individual_interest,
        'group_principal': group_principal,
        'group_interest': group_interest,
        'group_balance': group_principal + group_interest,
        'combined_principal': individual_principal + group_principal,
        'combined_interest': individual_interest + group_interest,
        'combined_balance': individual_principal + individual_interest + group_principal + group_interest,
        'individual_count': len(loans),
        'group_count': len(groups),
    }


def summarize_outstanding_portfolio():
    """(principal outstanding, interest outstanding) across both portfolios."""
    summary = summarize_portfolio()
    return float(summary['combined_principal']), float(summary['combined_interest'])


def loan_table_totals(loans):
    """Subtotals for the individual loan table (only the rows displayed)."""
    return {
        'principal': sum((_d(loan.principal) for loan in loans), ZERO),
        'current_due': sum((_d(loan.total_amount) for loan in loans), ZERO),
        'balance': sum((_d(loan.balance) for loan in loans), ZERO),
        'count': len(loans),
    }


def group_table_totals(groups):
    """Subtotals for the group loan table (only the rows displayed)."""
    return {
        'principal': sum((_d(group.principal) for group in groups), ZERO),
        'total': sum((_d(group.total_amount) for group in groups), ZERO),
        'amount_paid': sum((_d(group.amount_paid) for group in groups), ZERO),
        'balance': sum((_d(group.balance) for group in groups), ZERO),
        'count': len(groups),
    }
