from datetime import timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.utils.timezone import EAT_TIMEZONE, get_local_now


def _normalize_timestamp(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=EAT_TIMEZONE)
    return value.astimezone(EAT_TIMEZONE)


def consume_limit(scope, identifier, limit, window_seconds, block_seconds=None):
    from app.models.user import RateLimitState

    if not identifier:
        return True, 0

    now = get_local_now()
    block_seconds = block_seconds or window_seconds

    try:
        state = RateLimitState.query.filter_by(scope=scope, identifier=identifier).first()
        if not state:
            state = RateLimitState(
                scope=scope,
                identifier=identifier,
                request_count=0,
                window_started_at=now,
            )
            db.session.add(state)
            db.session.flush()

        state.window_started_at = _normalize_timestamp(state.window_started_at)
        state.blocked_until = _normalize_timestamp(state.blocked_until)

        if state.blocked_until and state.blocked_until > now:
            retry_after = max(int((state.blocked_until - now).total_seconds()), 1)
            return False, retry_after

        if not state.window_started_at or (now - state.window_started_at).total_seconds() > window_seconds:
            state.window_started_at = now
            state.request_count = 0
            state.blocked_until = None

        state.request_count = (state.request_count or 0) + 1
        state.updated_at = now

        if state.request_count > limit:
            state.blocked_until = now + timedelta(seconds=block_seconds)
            db.session.commit()
            return False, block_seconds

        db.session.commit()
        return True, 0
    except SQLAlchemyError:
        db.session.rollback()
        return True, 0


def clear_limit(scope, identifier):
    from app.models.user import RateLimitState

    if not identifier:
        return

    try:
        state = RateLimitState.query.filter_by(scope=scope, identifier=identifier).first()
        if not state:
            return
        db.session.delete(state)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
