"""Optional error monitoring with Sentry.

Enabled only when SENTRY_DSN is set. Errors logged with logger.exception()
(for example a failed dashboard calculation or audit write) are reported too.

Privacy: borrower ID numbers, form contents, cookies and auth headers never
leave the server. Events keep only the URL, method and stack trace.
"""
import os

SENSITIVE_HEADERS = {'cookie', 'authorization', 'x-csrftoken', 'x-api-key'}


def _scrub(event, hint=None):
    request = event.get('request') or {}
    for key in ('data', 'cookies', 'query_string', 'env'):
        request.pop(key, None)
    headers = request.get('headers')
    if isinstance(headers, dict):
        request['headers'] = {k: v for k, v in headers.items() if k.lower() not in SENSITIVE_HEADERS}
    event.pop('user', None)
    return event


def init_monitoring(app):
    dsn = (os.getenv('SENTRY_DSN') or '').strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
    except ImportError:
        app.logger.warning('SENTRY_DSN is set but sentry-sdk is not installed; monitoring disabled.')
        return False

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FlaskIntegration()],
        environment=os.getenv('SENTRY_ENVIRONMENT') or os.getenv('FLASK_ENV', 'development'),
        release=os.getenv('RENDER_GIT_COMMIT') or None,
        send_default_pii=False,
        max_request_body_size='never',
        include_local_variables=False,
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0') or 0),
        before_send=_scrub,
    )
    app.logger.info('Sentry error monitoring enabled.')
    return True
