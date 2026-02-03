"""Timezone utilities for East Africa Time (UTC+3) and Germany (CET/CEST)"""
from datetime import datetime, date, timedelta, timezone

# East Africa Time (UTC+3) timezone - Uganda
EAT_TIMEZONE = timezone(timedelta(hours=3))

# Central European Time (UTC+1) / Central European Summer Time (UTC+2) - Germany
# For simplicity, we'll use UTC+1 for CET (winter) and UTC+2 for CEST (summer)
# DST in Germany: last Sunday of March to last Sunday of October
CET_TIMEZONE = timezone(timedelta(hours=1))
CEST_TIMEZONE = timezone(timedelta(hours=2))


def is_dst_germany(dt):
    """Check if a given datetime falls in German DST (CEST) period"""
    year = dt.year
    # DST starts last Sunday of March at 2:00 AM
    march_last = datetime(year, 3, 31, 2, 0)
    while march_last.weekday() != 6:  # 6 = Sunday
        march_last -= timedelta(days=1)

    # DST ends last Sunday of October at 3:00 AM
    october_last = datetime(year, 10, 31, 3, 0)
    while october_last.weekday() != 6:
        october_last -= timedelta(days=1)

    # Convert to naive datetime for comparison
    naive_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
    return march_last <= naive_dt < october_last


def get_germany_timezone():
    """Get current Germany timezone (CET or CEST based on DST)"""
    now = datetime.utcnow()
    if is_dst_germany(now):
        return CEST_TIMEZONE
    return CET_TIMEZONE


def get_local_now():
    """Get current datetime in local timezone (UTC+3 East Africa Time)"""
    return datetime.now(EAT_TIMEZONE)


def get_local_today():
    """Get current date in local timezone"""
    return get_local_now().date()


def convert_to_dual_timezone(dt):
    """
    Convert a datetime to both Uganda (EAT) and Germany (CET/CEST) timezones
    Returns a dict with both timezone representations
    """
    if dt is None:
        return None

    # Ensure we have timezone info, assume EAT if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=EAT_TIMEZONE)

    # Convert to both timezones
    utc_dt = dt.astimezone(timezone.utc)
    eat_dt = utc_dt.astimezone(EAT_TIMEZONE)

    # Get appropriate German timezone
    germany_tz = get_germany_timezone()
    germany_dt = utc_dt.astimezone(germany_tz)
    tz_name = "CEST" if germany_tz == CEST_TIMEZONE else "CET"

    return {
        'uganda': {
            'datetime': eat_dt,
            'formatted': eat_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'timezone': 'EAT (UTC+3)'
        },
        'germany': {
            'datetime': germany_dt,
            'formatted': germany_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'timezone': f'{tz_name} (UTC+{"2" if tz_name == "CEST" else "1"})'
        }
    }
