"""Authoritative business metrics for the manager dashboard and reports.

Definitions (keep these in sync with any page that shows the same figure):

Sales value
    Full value of retail sales dated in the period (Sale.total_amount).
    A credit sale counts in full on its sale date. Loan repayments are never sales.
Cash received
    Money that actually came in during the period, by the date it came in:
      retail cash at sale   = amount paid at the counter (amount_paid minus
                              any later credit payments on that sale)
      credit collections    = credit payments dated in the period
      hire collections      = deposits taken on the hire date + hire payments
      loan collections      = individual loan payments (principal + interest),
                              including interest paid in cash at renewal
      group collections     = group loan payments
Gross profit (retail)
    Sales value minus the cost of goods sold, using the cost recorded at the
    moment of sale. Older lines without a recorded cost use today's stock cost
    and are flagged as estimated. Lines with no known cost are left out of
    profit and reported as unknown instead of being treated as 100% margin.
Interest earned
    Interest collected on individual and group loans. Principal repaid is not
    income. Each group instalment carries interest in the same proportion as
    the loan (interest : total).
Net profit
    Retail gross profit + interest earned + hire income
    - operating expenses - principal written off.
    Only reported once expenses are being recorded; without expense data a
    "net profit" figure would overstate the business.
"""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models.boutique import (
    BoutiqueCreditPayment, BoutiqueHire, BoutiqueHirePayment, BoutiqueSale, BoutiqueSaleItem, BoutiqueStock,
)
from app.models.expense import Expense
from app.models.finance import GroupLoan, GroupLoanPayment, Loan, LoanAdjustment, LoanPayment
from app.models.hardware import HardwareCreditPayment, HardwareSale, HardwareSaleItem, HardwareStock
from app.services.loan_accounting import summarize_portfolio

ZERO = Decimal('0')

RETAIL_UNITS = {
    'boutique': (BoutiqueSale, BoutiqueSaleItem, BoutiqueStock, BoutiqueCreditPayment),
    'hardware': (HardwareSale, HardwareSaleItem, HardwareStock, HardwareCreditPayment),
}


def _d(value):
    return Decimal(str(value or 0))


def growth_pct(current, previous):
    """Percentage change, or None when there is no previous value to compare."""
    current = _d(current)
    previous = _d(previous)
    if previous == 0:
        return None
    # Divide by the size of the previous value so a move from a loss towards
    # profit reads as an increase.
    return float((current - previous) / abs(previous) * 100)


def margin_pct(profit, revenue):
    revenue = _d(revenue)
    if revenue == 0:
        return None
    return float(_d(profit) / revenue * 100)


# ---------------------------------------------------------------------------
# Retail
# ---------------------------------------------------------------------------

def _branch_filter(sale_model, branch):
    if branch and hasattr(sale_model, 'branch'):
        return [sale_model.branch == branch]
    return []


def retail_unit_summary(unit, start, end, branch=None):
    """Sales, cash and gross profit for one retail unit between two dates.

    `branch` ('K' or 'M') narrows boutique figures to one branch.
    """
    sale_model, item_model, stock_model, credit_model = RETAIL_UNITS[unit]
    branch_clause = _branch_filter(sale_model, branch)

    credit_totals = db.session.query(
        credit_model.sale_id.label('sale_id'),
        func.sum(credit_model.amount).label('paid_later'),
    ).group_by(credit_model.sale_id).subquery()

    sales_value, transactions, cash_at_sale = db.session.query(
        func.coalesce(func.sum(sale_model.total_amount), 0),
        func.count(sale_model.id),
        func.coalesce(func.sum(sale_model.amount_paid - func.coalesce(credit_totals.c.paid_later, 0)), 0),
    ).outerjoin(
        credit_totals, credit_totals.c.sale_id == sale_model.id
    ).filter(
        sale_model.sale_date >= start,
        sale_model.sale_date <= end,
        sale_model.is_deleted == False,  # noqa: E712
        *branch_clause,
    ).one()

    credit_collections = db.session.query(
        func.coalesce(func.sum(credit_model.amount), 0)
    ).join(
        sale_model, credit_model.sale_id == sale_model.id
    ).filter(
        credit_model.payment_date >= start,
        credit_model.payment_date <= end,
        sale_model.is_deleted == False,  # noqa: E712
        *branch_clause,
    ).scalar()

    lines = db.session.query(
        item_model.quantity,
        item_model.unit_price,
        item_model.subtotal,
        item_model.unit_cost_at_sale,
        stock_model.cost_price,
    ).join(
        sale_model, item_model.sale_id == sale_model.id
    ).outerjoin(
        stock_model, item_model.stock_id == stock_model.id
    ).filter(
        sale_model.sale_date >= start,
        sale_model.sale_date <= end,
        sale_model.is_deleted == False,  # noqa: E712
        *branch_clause,
    ).all()

    cogs = ZERO
    costed_revenue = ZERO
    estimated_lines = 0
    unknown_lines = 0
    unknown_revenue = ZERO
    for quantity, unit_price, subtotal, cost_at_sale, current_cost in lines:
        revenue = _d(subtotal) if subtotal is not None else _d(unit_price) * _d(quantity)
        if cost_at_sale is not None:
            cost = _d(cost_at_sale)
        elif current_cost is not None:
            cost = _d(current_cost)
            estimated_lines += 1
        else:
            unknown_lines += 1
            unknown_revenue += revenue
            continue
        cogs += cost * _d(quantity)
        costed_revenue += revenue

    sales_value = _d(sales_value)
    cash_at_sale = _d(cash_at_sale)
    gross_profit = costed_revenue - cogs
    return {
        'sales_value': sales_value,
        'transactions': int(transactions or 0),
        'cash_at_sale': cash_at_sale,
        'credit_sales': max(sales_value - cash_at_sale, ZERO),
        'credit_collections': _d(credit_collections),
        'cash_received': cash_at_sale + _d(credit_collections),
        'cogs': cogs,
        'gross_profit': gross_profit,
        'gross_margin_pct': margin_pct(gross_profit, costed_revenue),
        'estimated_cost_lines': estimated_lines,
        'unknown_cost_lines': unknown_lines,
        'unknown_cost_revenue': unknown_revenue,
    }


def retail_receivables(unit, branch=None):
    sale_model = RETAIL_UNITS[unit][0]
    return _d(db.session.query(func.coalesce(func.sum(sale_model.balance), 0)).filter(
        sale_model.is_credit_cleared == False,  # noqa: E712
        sale_model.is_deleted == False,  # noqa: E712
        sale_model.balance > 0,
        *_branch_filter(sale_model, branch),
    ).scalar())


def hire_collections(start, end):
    deposits = db.session.query(func.coalesce(func.sum(BoutiqueHire.deposit_amount), 0)).filter(
        BoutiqueHire.hire_date >= start,
        BoutiqueHire.hire_date <= end,
        BoutiqueHire.is_deleted == False,  # noqa: E712
    ).scalar()
    payments = db.session.query(func.coalesce(func.sum(BoutiqueHirePayment.amount), 0)).join(
        BoutiqueHire, BoutiqueHirePayment.hire_id == BoutiqueHire.id
    ).filter(
        BoutiqueHirePayment.payment_date >= start,
        BoutiqueHirePayment.payment_date <= end,
        BoutiqueHire.is_deleted == False,  # noqa: E712
    ).scalar()
    return _d(deposits) + _d(payments)


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

def loan_collections(start, end):
    def _sum(column, renewal_only=False):
        query = db.session.query(func.coalesce(func.sum(column), 0)).join(
            Loan, LoanPayment.loan_id == Loan.id
        ).filter(
            LoanPayment.payment_date >= start,
            LoanPayment.payment_date <= end,
            LoanPayment.is_deleted == False,  # noqa: E712
            Loan.is_deleted == False,  # noqa: E712
        )
        if renewal_only:
            query = query.filter(LoanPayment.payment_type == 'renewal')
        return _d(query.scalar())

    group_total = _d(db.session.query(func.coalesce(func.sum(GroupLoanPayment.amount), 0)).join(
        GroupLoan, GroupLoanPayment.group_loan_id == GroupLoan.id
    ).filter(
        GroupLoanPayment.payment_date >= start,
        GroupLoanPayment.payment_date <= end,
        GroupLoanPayment.is_deleted == False,  # noqa: E712
        GroupLoan.is_deleted == False,  # noqa: E712
    ).scalar())

    # Renewal settlements are paid in cash by the borrower, so they are included.
    principal = _sum(LoanPayment.principal_amount)
    interest = _sum(LoanPayment.interest_amount)
    group_interest = group_interest_collected(start, end)
    return {
        'individual_principal': principal,
        'individual_interest': interest,
        'individual_total': principal + interest,
        'group_total': group_total,
        'group_interest': group_interest,
        'group_principal': group_total - group_interest,
        'total': principal + interest + group_total,
        'renewal_settlements': _sum(LoanPayment.amount, renewal_only=True),
    }


def group_interest_collected(start, end):
    """Interest share of group payments dated in the period.

    A group instalment is "a sum of both": each payment carries interest in
    the same proportion as the loan (interest : total).
    """
    rows = db.session.query(
        GroupLoanPayment.amount, GroupLoan.interest_amount, GroupLoan.total_amount
    ).join(GroupLoan, GroupLoanPayment.group_loan_id == GroupLoan.id).filter(
        GroupLoanPayment.payment_date >= start,
        GroupLoanPayment.payment_date <= end,
        GroupLoanPayment.is_deleted == False,  # noqa: E712
        GroupLoan.is_deleted == False,  # noqa: E712
    ).all()
    total = ZERO
    for amount, interest_amount, total_amount in rows:
        if _d(total_amount) > 0:
            total += (_d(amount) * _d(interest_amount) / _d(total_amount)).quantize(Decimal('1'))
    return total


def expenses_total(start, end):
    return _d(db.session.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.expense_date >= start,
        Expense.expense_date <= end,
        Expense.is_deleted == False,  # noqa: E712
    ).scalar())


def expenses_by_unit(start, end):
    """Expenses per business unit; every unit carries its own costs."""
    rows = dict(db.session.query(Expense.business_unit, func.coalesce(func.sum(Expense.amount), 0)).filter(
        Expense.expense_date >= start,
        Expense.expense_date <= end,
        Expense.is_deleted == False,  # noqa: E712
    ).group_by(Expense.business_unit).all())
    return {unit: _d(rows.get(unit)) for unit in ('boutique', 'hardware', 'finance', 'shared')}


def principal_written_off(start, end):
    return _d(db.session.query(func.coalesce(func.sum(LoanAdjustment.amount), 0)).filter(
        LoanAdjustment.adjustment_type == 'principal_write_off',
        LoanAdjustment.is_reversed == False,  # noqa: E712
        LoanAdjustment.effective_date >= start,
        LoanAdjustment.effective_date <= end,
    ).scalar())


def expenses_recorded():
    return db.session.query(Expense.query.filter(Expense.is_deleted == False).exists()).scalar()  # noqa: E712


# ---------------------------------------------------------------------------
# Period summary
# ---------------------------------------------------------------------------

def period_summary(start, end):
    """Every headline figure for a date range, built from the definitions above."""
    boutique = retail_unit_summary('boutique', start, end)
    hardware = retail_unit_summary('hardware', start, end)
    hire = hire_collections(start, end)
    loans = loan_collections(start, end)
    expenses = expenses_total(start, end)
    unit_expenses = expenses_by_unit(start, end)
    write_offs = principal_written_off(start, end)

    sales_value = boutique['sales_value'] + hardware['sales_value']
    gross_profit = boutique['gross_profit'] + hardware['gross_profit']
    retail_cash = boutique['cash_received'] + hardware['cash_received']
    cash_breakdown = {
        'retail_at_sale': boutique['cash_at_sale'] + hardware['cash_at_sale'],
        'retail_credit_collections': boutique['credit_collections'] + hardware['credit_collections'],
        'hire': hire,
        'loan_principal': loans['individual_principal'],
        'loan_interest': loans['individual_interest'],
        'group_loans': loans['group_total'],
    }
    return {
        'start': start,
        'end': end,
        'sales_value': sales_value,
        'transactions': boutique['transactions'] + hardware['transactions'],
        'cash_received': retail_cash + hire + loans['total'],
        'cash_breakdown': cash_breakdown,
        'gross_profit': gross_profit,
        'gross_margin_pct': margin_pct(
            gross_profit,
            sales_value - boutique['unknown_cost_revenue'] - hardware['unknown_cost_revenue'],
        ),
        'estimated_cost_lines': boutique['estimated_cost_lines'] + hardware['estimated_cost_lines'],
        'unknown_cost_lines': boutique['unknown_cost_lines'] + hardware['unknown_cost_lines'],
        'interest_earned': loans['individual_interest'] + loans['group_interest'],
        'hire_income': hire,
        'expenses': expenses,
        'write_offs': write_offs,
        'net_profit': gross_profit + loans['individual_interest'] + loans['group_interest'] + hire - expenses - write_offs,
        'expenses_by_unit': unit_expenses,
        # Each unit's own result: its income minus its own expenses.
        'unit_profit': {
            'boutique': boutique['gross_profit'] + hire - unit_expenses['boutique'],
            'hardware': hardware['gross_profit'] - unit_expenses['hardware'],
            'finance': (loans['individual_interest'] + loans['group_interest']
                        - unit_expenses['finance'] - write_offs),
        },
        'loans': loans,
        'boutique': boutique,
        'hardware': hardware,
    }


def inventory_summary():
    def _value(model):
        return _d(db.session.query(func.coalesce(func.sum(model.cost_price * model.quantity), 0)).filter(
            model.is_active == True  # noqa: E712
        ).scalar())

    def _low(model):
        return model.query.filter(
            model.is_active == True,  # noqa: E712
            model.low_stock_threshold.isnot(None),
            model.quantity <= model.low_stock_threshold,
        )

    boutique_value = _value(BoutiqueStock)
    hardware_value = _value(HardwareStock)
    low_items = []
    for label, model in (('Boutique', BoutiqueStock), ('Hardware', HardwareStock)):
        for item in _low(model).order_by(model.quantity.asc()).limit(5).all():
            low_items.append({'business': label, 'item': item.item_name, 'quantity': item.quantity, 'unit': item.unit})
    return {
        'boutique_value': boutique_value,
        'hardware_value': hardware_value,
        'total_value': boutique_value + hardware_value,
        'boutique_low': _low(BoutiqueStock).count(),
        'hardware_low': _low(HardwareStock).count(),
        'low_items': low_items,
    }


def manager_dashboard(today):
    """Everything the manager dashboard shows, compared like-for-like with yesterday."""
    yesterday = today - timedelta(days=1)
    current = period_summary(today, today)
    previous = period_summary(yesterday, yesterday)

    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        summary = current if day == today else (previous if day == yesterday else period_summary(day, day))
        trend.append({
            'date': day,
            'label': day.strftime('%a'),
            'sales_value': summary['sales_value'],
            'cash_received': summary['cash_received'],
            'gross_profit': summary['gross_profit'],
        })

    portfolio = summarize_portfolio()
    overdue_loans = Loan.query.filter(
        Loan.is_deleted == False, Loan.status == 'overdue', Loan.balance > 0  # noqa: E712
    ).count()
    overdue_groups = GroupLoan.query.filter(
        GroupLoan.is_deleted == False, GroupLoan.status == 'overdue', GroupLoan.balance > 0  # noqa: E712
    ).count()

    receivables = {unit: retail_receivables(unit) for unit in RETAIL_UNITS}
    return {
        'today': current,
        'yesterday': previous,
        'growth': {
            'sales_value': growth_pct(current['sales_value'], previous['sales_value']),
            'cash_received': growth_pct(current['cash_received'], previous['cash_received']),
            'gross_profit': growth_pct(current['gross_profit'], previous['gross_profit']),
            'interest_earned': growth_pct(current['interest_earned'], previous['interest_earned']),
            'net_profit': growth_pct(current['net_profit'], previous['net_profit']),
        },
        'show_net_profit': expenses_recorded(),
        'trend': trend,
        'portfolio': portfolio,
        'overdue_loans': overdue_loans,
        'overdue_groups': overdue_groups,
        'receivables': receivables,
        'receivables_total': sum(receivables.values(), ZERO),
        'inventory': inventory_summary(),
    }
