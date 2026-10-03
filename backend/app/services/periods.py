"""Shared reporting periods and like-for-like comparison periods."""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

PERIOD_CHOICES = (
    ('today', 'Today'),
    ('7d', 'Last 7 days'),
    ('month', 'This month'),
    ('last_month', 'Last month'),
    ('custom', 'Custom'),
)
MAX_CUSTOM_DAYS = 366


def _parse(value):
    try:
        return date.fromisoformat(str(value or '').strip())
    except ValueError:
        return None


def resolve_period(args, today, default='month'):
    """Turn request args into a reporting period plus the period it is compared with.

    Comparisons are like-for-like: today vs yesterday, last 7 days vs the 7 days
    before, this month so far vs the same number of days last month, last month
    vs the month before, and a custom range vs the equally long range before it.
    """
    key = (args.get('period') or default).strip()
    if key not in dict(PERIOD_CHOICES):
        key = default

    if key == 'today':
        start = end = today
        prev_start = prev_end = today - timedelta(days=1)
    elif key == '7d':
        start, end = today - timedelta(days=6), today
        prev_start, prev_end = start - timedelta(days=7), start - timedelta(days=1)
    elif key == 'last_month':
        start = (today.replace(day=1) - relativedelta(months=1))
        end = today.replace(day=1) - timedelta(days=1)
        prev_start = start - relativedelta(months=1)
        prev_end = start - timedelta(days=1)
    elif key == 'custom':
        start = _parse(args.get('start')) or today.replace(day=1)
        end = _parse(args.get('end')) or today
        if end < start:
            start, end = end, start
        if (end - start).days > MAX_CUSTOM_DAYS:
            start = end - timedelta(days=MAX_CUSTOM_DAYS)
        length = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length - 1)
    else:  # this month so far
        start, end = today.replace(day=1), today
        prev_start = start - relativedelta(months=1)
        prev_end = min(prev_start + timedelta(days=(end - start).days), start - timedelta(days=1))

    return {
        'key': key,
        'label': dict(PERIOD_CHOICES)[key],
        'start': start,
        'end': end,
        'prev_start': prev_start,
        'prev_end': prev_end,
        'choices': PERIOD_CHOICES,
    }
