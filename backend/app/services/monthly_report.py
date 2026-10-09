"""Data for the manager's monthly PDF report.

Everything comes from business_metrics.period_summary, so the report agrees
with the dashboard and analytics pages.
"""
from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from app.extensions import db
from app.services.analytics import STOCK, UNIT_LABELS
from app.services.business_metrics import inventory_summary, period_summary

ZERO = Decimal('0')


def _d(value):
    return Decimal(str(value or 0))


def _month_bounds(month_start, today):
    end = month_start + relativedelta(months=1) - timedelta(days=1)
    return month_start, min(end, today)


def product_ranking(start, end):
    """Every stock item with units sold and revenue in the period (zero if unsold)."""
    rows = []
    for unit, (stock_model, _, sale_model, item_model) in STOCK.items():
        sold = dict((stock_id, (int(qty or 0), _d(revenue))) for stock_id, qty, revenue in db.session.query(
            item_model.stock_id, func.sum(item_model.quantity), func.sum(item_model.subtotal)
        ).join(sale_model, item_model.sale_id == sale_model.id).filter(
            sale_model.sale_date >= start, sale_model.sale_date <= end,
            sale_model.is_deleted == False, item_model.stock_id.isnot(None),  # noqa: E712
        ).group_by(item_model.stock_id).all())
        for item in stock_model.query.filter(stock_model.is_active == True).all():  # noqa: E712
            quantity, revenue = sold.get(item.id, (0, ZERO))
            rows.append({'unit': UNIT_LABELS[unit], 'item': item.item_name, 'quantity': quantity,
                         'revenue': revenue, 'in_stock': item.quantity})
    return rows


def build_monthly_report(month_start, today):
    """Report for `month_start`'s month, compared with the two months before it."""
    month_start = month_start.replace(day=1)
    months = []
    for offset in (2, 1, 0):
        start = month_start - relativedelta(months=offset)
        start, end = _month_bounds(start, today)
        summary = period_summary(start, end)
        months.append({
            'label': start.strftime('%b %Y'),
            'start': start,
            'end': end,
            'summary': summary,
            'partial': end < start + relativedelta(months=1) - timedelta(days=1),
        })

    # Weekly profit across the same three months (weeks start on Monday).
    weeks = []
    first_day = months[0]['start']
    last_day = months[-1]['end']
    week_start = first_day - timedelta(days=first_day.weekday())
    while week_start <= last_day:
        start = max(week_start, first_day)
        end = min(week_start + timedelta(days=6), last_day)
        summary = period_summary(start, end)
        weeks.append({
            'label': f"{start.strftime('%d %b')} - {end.strftime('%d %b')}",
            'sales_value': summary['sales_value'],
            'gross_profit': summary['gross_profit'],
            'interest_earned': summary['interest_earned'],
            'expenses': summary['expenses'],
            'net_profit': summary['net_profit'],
        })
        week_start += timedelta(days=7)

    current = months[-1]
    ranking = product_ranking(current['start'], current['end'])
    sold = sorted((row for row in ranking if row['quantity'] > 0), key=lambda row: row['quantity'], reverse=True)
    unsold = sorted((row for row in ranking if row['quantity'] == 0 and row['in_stock'] > 0),
                    key=lambda row: row['in_stock'], reverse=True)
    least = sorted((row for row in ranking if row['in_stock'] > 0 or row['quantity'] > 0),
                   key=lambda row: (row['quantity'], -row['in_stock']))

    return {
        'title_month': current['start'].strftime('%B %Y'),
        'months': months,
        'weeks': weeks,
        'inventory': inventory_summary(),
        'best_sellers': sold[:5],
        'least_sellers': least[:5],
        'unsold_count': len(unsold),
        'generated_on': today,
    }
