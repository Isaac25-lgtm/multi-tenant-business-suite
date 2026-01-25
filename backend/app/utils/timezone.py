"""Timezone utilities for East Africa Time (UTC+3)"""
from datetime import datetime, date, timedelta, timezone

# East Africa Time (UTC+3) timezone
EAT_TIMEZONE = timezone(timedelta(hours=3))


def get_local_now():
    """Get current datetime in local timezone (UTC+3 East Africa Time)"""
    return datetime.now(EAT_TIMEZONE)


def get_local_today():
    """Get current date in local timezone"""
    return get_local_now().date()
