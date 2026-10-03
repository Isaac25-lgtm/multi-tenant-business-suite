"""Manager drill-down analytics: retail, finance portfolio, inventory.

Every figure is built from app.services.business_metrics and
app.services.loan_accounting, so these pages agree with the dashboard.
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from app.extensions import db
from app.models.boutique import BoutiqueCategory, BoutiqueSale, BoutiqueSaleItem, BoutiqueStock
from app.models.finance import GroupLoan, Loan, LoanAdjustment, LoanClient
from app.models.hardware import HardwareCategory, HardwareSale, HardwareSaleItem, HardwareStock
from app.services.business_metrics import (
    RETAIL_UNITS, growth_pct, loan_collections, margin_pct, retail_receivables, retail_unit_summary,
)
from app.services.loan_accounting import summarize_portfolio

ZERO = Decimal('0')
BRANCH_LABELS = {'K': 'Kapchorwa', 'M': 'Bukwo'}
STOCK = {
    'boutique': (BoutiqueStock, BoutiqueCategory, BoutiqueSale, BoutiqueSaleItem),
    'hardware': (HardwareStock, HardwareCategory, HardwareSale, HardwareSaleItem),
}
UNIT_LABELS = {'boutique': 'Boutique', 'hardware': 'Hardware'}


def _d(value):
    return Decimal(str(value or 0))


def _units(unit):
    return [unit] if unit in RETAIL_UNITS else list(RETAIL_UNITS)


def _trend_buckets(start, end):
    """Daily buckets for ranges up to ~2 months, otherwise monthly."""
    if (end - start).days <= 62:
        day = start
        while day <= end:
            yield day.strftime('%d %b'), day, day
            day += timedelta(days=1)
    else:
        month = start.replace(day=1)
        while month <= end:
            bucket_end = min(month + relativedelta(months=1) - timedelta(days=1), end)
            yield month.strftime('%b %Y'), max(month, start), bucket_end
            month += relativedelta(months=1)


# ---------------------------------------------------------------------------
# Retail
# ---------------------------------------------------------------------------

def _combine(summaries):
    keys = ('sales_value', 'cash_at_sale', 'credit_sales', 'credit_collections', 'cash_received', 'cogs',
            'gross_profit', 'unknown_cost_revenue')
    total = {key: sum((s[key] for s in summaries), ZERO) for key in keys}
    total['transactions'] = sum(s['transactions'] for s in summaries)
    total['estimated_cost_lines'] = sum(s['estimated_cost_lines'] for s in summaries)
    total['unknown_cost_lines'] = sum(s['unknown_cost_lines'] for s in summaries)
    total['gross_margin_pct'] = margin_pct(total['gross_profit'], total['sales_value'] - total['unknown_cost_revenue'])
    total['avg_transaction'] = (total['sales_value'] / total['transactions']) if total['transactions'] else None
    total['credit_ratio_pct'] = margin_pct(total['credit_sales'], total['sales_value'])
    return total


def _retail_totals(units, start, end, branch):
    return _combine([retail_unit_summary(u, start, end, branch if u == 'boutique' else None) for u in units])


def _top_products(units, start, end, branch, limit=10):
    rows = []
    for unit in units:
        stock_model, _, sale_model, item_model = STOCK[unit]
        filters = [sale_model.sale_date >= start, sale_model.sale_date <= end, sale_model.is_deleted == False]  # noqa: E712
        if branch and unit == 'boutique':
            filters.append(sale_model.branch == branch)
        cost = func.coalesce(item_model.unit_cost_at_sale, stock_model.cost_price)
        query = db.session.query(
            item_model.item_name,
            func.sum(item_model.quantity),
            func.sum(item_model.subtotal),
            func.sum(item_model.quantity * cost),
            func.count(cost) == func.count(item_model.id),
        ).join(sale_model, item_model.sale_id == sale_model.id).outerjoin(
            stock_model, item_model.stock_id == stock_model.id
        ).filter(*filters).group_by(item_model.item_name)
        for name, qty, revenue, cogs, cost_known in query.all():
            revenue = _d(revenue)
            rows.append({
                'unit': UNIT_LABELS[unit],
                'item': name,
                'quantity': int(qty or 0),
                'revenue': revenue,
                'gross_profit': (revenue - _d(cogs)) if cost_known else None,
            })
    rows.sort(key=lambda row: row['revenue'], reverse=True)
    return rows[:limit]


def _slow_movers(units, start, end, branch, limit=10):
    """Active items with stock on hand that sold nothing in the period."""
    rows = []
    for unit in units:
        stock_model, _, sale_model, item_model = STOCK[unit]
        sold = db.session.query(item_model.stock_id).join(
            sale_model, item_model.sale_id == sale_model.id
        ).filter(
            sale_model.sale_date >= start, sale_model.sale_date <= end,
            sale_model.is_deleted == False, item_model.stock_id.isnot(None),  # noqa: E712
        )
        query = stock_model.query.filter(
            stock_model.is_active == True, stock_model.quantity > 0, ~stock_model.id.in_(sold),  # noqa: E712
        )
        if branch and unit == 'boutique':
            query = query.filter(stock_model.branch == branch)
        for item in query.all():
            rows.append({
                'unit': UNIT_LABELS[unit],
                'item': item.item_name,
                'quantity': item.quantity,
                'value': _d(item.cost_price) * item.quantity,
            })
    rows.sort(key=lambda row: row['value'], reverse=True)
    return rows[:limit]


def retail_analytics(period, unit=None, branch=None):
    branch = branch if branch in BRANCH_LABELS else None
    units = _units(unit)
    current = _retail_totals(units, period['start'], period['end'], branch)
    previous = _retail_totals(units, period['prev_start'], period['prev_end'], branch)

    by_unit = []
    for u in units:
        summary = retail_unit_summary(u, period['start'], period['end'], branch if u == 'boutique' else None)
        summary['label'] = UNIT_LABELS[u]
        summary['receivables'] = retail_receivables(u, branch if u == 'boutique' else None)
        by_unit.append(summary)

    by_branch = []
    if 'boutique' in units:
        for code, label in BRANCH_LABELS.items():
            summary = retail_unit_summary('boutique', period['start'], period['end'], code)
            summary['label'] = label
            summary['receivables'] = retail_receivables('boutique', code)
            by_branch.append(summary)

    trend = []
    for label, bucket_start, bucket_end in _trend_buckets(period['start'], period['end']):
        totals = _retail_totals(units, bucket_start, bucket_end, branch)
        trend.append({'label': label, 'sales_value': totals['sales_value'],
                      'cash_received': totals['cash_received'], 'gross_profit': totals['gross_profit']})

    receivables = sum((row['receivables'] for row in by_unit), ZERO)
    return {
        'current': current,
        'previous': previous,
        'growth': {key: growth_pct(current[key], previous[key])
                   for key in ('sales_value', 'cash_received', 'gross_profit', 'transactions')},
        'receivables': receivables,
        'by_unit': by_unit,
        'by_branch': by_branch,
        'trend': trend,
        'top_products': _top_products(units, period['start'], period['end'], branch),
        'slow_movers': _slow_movers(units, period['start'], period['end'], branch),
        'unit': unit if unit in RETAIL_UNITS else 'all',
        'branch': branch,
    }


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

AGING_BUCKETS = (
    ('current', 'Not yet due', None, 0),
    ('1_30', '1–30 days overdue', 1, 30),
    ('31_60', '31–60 days overdue', 31, 60),
    ('61_90', '61–90 days overdue', 61, 90),
    ('90_plus', 'Over 90 days overdue', 91, None),
)


def _aging_key(days_overdue):
    for key, _, low, high in AGING_BUCKETS:
        if low is None and days_overdue <= 0:
            return key
        if low is not None and days_overdue >= low and (high is None or days_overdue <= high):
            return key
    return 'current'


def finance_analytics(period, today):
    open_loans = Loan.query.filter(Loan.is_deleted == False, Loan.status != 'renewed', Loan.balance > 0).all()  # noqa: E712
    open_groups = GroupLoan.query.filter(GroupLoan.is_deleted == False, GroupLoan.balance > 0).all()  # noqa: E712
    portfolio = summarize_portfolio(open_loans, open_groups)

    aging = {key: {'label': label, 'count': 0, 'principal': ZERO, 'balance': ZERO}
             for key, label, _, _ in AGING_BUCKETS}
    overdue_list = []
    for record, kind in [(loan, 'Individual') for loan in open_loans] + [(group, 'Group') for group in open_groups]:
        days = (today - record.due_date).days if record.due_date else 0
        bucket = aging[_aging_key(days)]
        bucket['count'] += 1
        bucket['principal'] += _d(record.outstanding_principal)
        bucket['balance'] += _d(record.balance)
        if days > 0:
            overdue_list.append({
                'kind': kind,
                'name': record.client.name if kind == 'Individual' and record.client else getattr(record, 'group_name', ''),
                'id': record.id,
                'days': days,
                'balance': _d(record.balance),
                'principal': _d(record.outstanding_principal),
            })
    overdue_list.sort(key=lambda row: row['balance'], reverse=True)

    over_30 = sum((aging[key]['principal'] for key in ('31_60', '61_90', '90_plus')), ZERO)
    par30 = (float(over_30 / portfolio['combined_principal'] * 100)
             if portfolio['combined_principal'] > 0 else None)

    collections = loan_collections(period['start'], period['end'])
    previous = loan_collections(period['prev_start'], period['prev_end'])

    status_counts = dict(db.session.query(Loan.status, func.count(Loan.id)).filter(
        Loan.is_deleted == False  # noqa: E712
    ).group_by(Loan.status).all())
    group_status_counts = dict(db.session.query(GroupLoan.status, func.count(GroupLoan.id)).filter(
        GroupLoan.is_deleted == False  # noqa: E712
    ).group_by(GroupLoan.status).all())

    adjustments = db.session.query(LoanAdjustment.adjustment_type, func.sum(LoanAdjustment.amount)).filter(
        LoanAdjustment.is_reversed == False,  # noqa: E712
        LoanAdjustment.effective_date >= period['start'],
        LoanAdjustment.effective_date <= period['end'],
    ).group_by(LoanAdjustment.adjustment_type).all()

    trend = []
    month = today.replace(day=1) - relativedelta(months=5)
    for _ in range(6):
        month_end = min(month + relativedelta(months=1) - timedelta(days=1), today)
        totals = loan_collections(month, month_end)
        trend.append({'label': month.strftime('%b %Y'), 'principal': totals['individual_principal'] + totals['group_principal'],
                      'interest': totals['individual_interest'] + totals['group_interest'], 'total': totals['total']})
        month += relativedelta(months=1)

    return {
        'portfolio': portfolio,
        'aging': [aging[key] for key, *_ in AGING_BUCKETS],
        'par30': par30,
        'overdue_list': overdue_list[:15],
        'collections': collections,
        'previous_collections': previous,
        'growth': {
            'total': growth_pct(collections['total'], previous['total']),
            'interest': growth_pct(collections['individual_interest'] + collections['group_interest'],
                                   previous['individual_interest'] + previous['group_interest']),
        },
        'status_counts': status_counts,
        'group_status_counts': group_status_counts,
        'client_count': LoanClient.query.filter_by(is_active=True).count(),
        'adjustments': [(LoanAdjustment.TYPES.get(kind, kind), _d(amount)) for kind, amount in adjustments],
        'trend': trend,
    }


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

def inventory_analytics(period):
    units = []
    by_category = []
    low_items = []
    for unit, (stock_model, category_model, sale_model, item_model) in STOCK.items():
        active = stock_model.query.filter(stock_model.is_active == True)  # noqa: E712
        value = _d(db.session.query(func.coalesce(func.sum(stock_model.cost_price * stock_model.quantity), 0)).filter(
            stock_model.is_active == True).scalar())  # noqa: E712
        low_query = active.filter(stock_model.low_stock_threshold.isnot(None),
                                  stock_model.quantity <= stock_model.low_stock_threshold, stock_model.quantity > 0)
        units.append({
            'label': UNIT_LABELS[unit],
            'value': value,
            'skus': active.filter(stock_model.quantity > 0).count(),
            'low': low_query.count(),
            'out': active.filter(stock_model.quantity <= 0).count(),
        })
        for name, cat_value, count in db.session.query(
            func.coalesce(category_model.name, 'Uncategorised'),
            func.sum(stock_model.cost_price * stock_model.quantity),
            func.count(stock_model.id),
        ).outerjoin(category_model, stock_model.category_id == category_model.id).filter(
            stock_model.is_active == True  # noqa: E712
        ).group_by(category_model.name).all():
            by_category.append({'unit': UNIT_LABELS[unit], 'category': name, 'value': _d(cat_value), 'items': count})
        for item in active.filter(stock_model.low_stock_threshold.isnot(None),
                                  stock_model.quantity <= stock_model.low_stock_threshold).order_by(
                                      stock_model.quantity.asc()).limit(20).all():
            low_items.append({'unit': UNIT_LABELS[unit], 'item': item.item_name, 'quantity': item.quantity,
                              'threshold': item.low_stock_threshold, 'unit_name': item.unit})

    by_branch = []
    for code, label in BRANCH_LABELS.items():
        branch_value = _d(db.session.query(func.coalesce(func.sum(BoutiqueStock.cost_price * BoutiqueStock.quantity), 0)).filter(
            BoutiqueStock.is_active == True, BoutiqueStock.branch == code).scalar())  # noqa: E712
        by_branch.append({'label': label, 'value': branch_value})

    by_category.sort(key=lambda row: row['value'], reverse=True)
    sellers = defaultdict(lambda: {'quantity': 0, 'revenue': ZERO})
    for unit, (stock_model, _, sale_model, item_model) in STOCK.items():
        for name, qty, revenue in db.session.query(
            item_model.item_name, func.sum(item_model.quantity), func.sum(item_model.subtotal)
        ).join(sale_model, item_model.sale_id == sale_model.id).filter(
            sale_model.sale_date >= period['start'], sale_model.sale_date <= period['end'],
            sale_model.is_deleted == False,  # noqa: E712
        ).group_by(item_model.item_name).all():
            entry = sellers[(UNIT_LABELS[unit], name)]
            entry['quantity'] += int(qty or 0)
            entry['revenue'] += _d(revenue)
    top_sellers = sorted(
        ({'unit': unit, 'item': item, **data} for (unit, item), data in sellers.items()),
        key=lambda row: row['quantity'], reverse=True,
    )[:10]

    return {
        'units': units,
        'total_value': sum((u['value'] for u in units), ZERO),
        'skus': sum(u['skus'] for u in units),
        'low': sum(u['low'] for u in units),
        'out': sum(u['out'] for u in units),
        'by_category': by_category,
        'by_branch': by_branch,
        'low_items': low_items,
        'top_sellers': top_sellers,
        'slow_movers': _slow_movers(list(STOCK), period['start'], period['end'], None, limit=15),
    }
