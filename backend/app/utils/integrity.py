"""Guards against duplicate financial submissions.

Payment routes lock the parent row (SELECT ... FOR UPDATE) before checking,
so two simultaneous submissions are serialised and the second one sees the
first one's committed payment.
"""
from datetime import timedelta

from sqlalchemy import func

DUPLICATE_WINDOW_SECONDS = 120


def find_recent_duplicate(model, window_seconds=DUPLICATE_WINDOW_SECONDS, **filters):
    """Return an identical, non-deleted row created within the last few minutes.

    `created_at` is written as local wall-clock time in the database session's
    timezone, so it is compared with LOCALTIMESTAMP from the same session.
    """
    query = model.query.filter_by(**filters)
    if hasattr(model, 'is_deleted'):
        query = query.filter(model.is_deleted == False)  # noqa: E712
    cutoff = func.localtimestamp() - timedelta(seconds=window_seconds)
    return query.filter(model.created_at >= cutoff).first()


DUPLICATE_MESSAGE = (
    'An identical payment was recorded moments ago, so this one was not saved again. '
    'If it really is a second payment, wait two minutes and enter it again.'
)
