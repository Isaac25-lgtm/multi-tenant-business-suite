from datetime import date

from app.services.periods import resolve_period

TODAY = date(2026, 3, 15)


def _p(**args):
    return resolve_period(args, TODAY)


def test_today_compares_with_yesterday():
    p = _p(period='today')
    assert (p['start'], p['end']) == (TODAY, TODAY)
    assert (p['prev_start'], p['prev_end']) == (date(2026, 3, 14), date(2026, 3, 14))


def test_last_7_days_compares_with_the_7_before():
    p = _p(period='7d')
    assert (p['start'], p['end']) == (date(2026, 3, 9), TODAY)
    assert (p['prev_start'], p['prev_end']) == (date(2026, 3, 2), date(2026, 3, 8))


def test_month_to_date_compares_same_number_of_days():
    p = _p(period='month')
    assert (p['start'], p['end']) == (date(2026, 3, 1), TODAY)
    assert (p['prev_start'], p['prev_end']) == (date(2026, 2, 1), date(2026, 2, 15))


def test_month_to_date_never_spills_past_a_short_month():
    p = resolve_period({'period': 'month'}, date(2026, 3, 31))
    assert (p['prev_start'], p['prev_end']) == (date(2026, 2, 1), date(2026, 2, 28))


def test_last_month_compares_with_the_month_before():
    p = _p(period='last_month')
    assert (p['start'], p['end']) == (date(2026, 2, 1), date(2026, 2, 28))
    assert (p['prev_start'], p['prev_end']) == (date(2026, 1, 1), date(2026, 1, 31))


def test_custom_range_compares_with_equal_length_before_and_tolerates_bad_input():
    p = _p(period='custom', start='2026-03-10', end='2026-03-01')   # reversed
    assert (p['start'], p['end']) == (date(2026, 3, 1), date(2026, 3, 10))
    assert (p['prev_start'], p['prev_end']) == (date(2026, 2, 19), date(2026, 2, 28))
    assert _p(period='nonsense')['key'] == 'month'
    assert _p(period='custom', start='not-a-date')['start'] == date(2026, 3, 1)
