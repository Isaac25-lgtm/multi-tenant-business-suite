import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

WEAK_SECRETS = {
    None,
    '',
    'dev-secret-key-change-in-production',
    'dev-secret-key-change-in-production-12345',
}


def get_secret_key():
    """Get SECRET_KEY. In production, refuse to start with a weak or missing key."""
    env = os.getenv('FLASK_ENV', 'development')
    key = os.getenv('SECRET_KEY')

    if env == 'production':
        if key in WEAK_SECRETS or (key and len(key) < 32):
            raise RuntimeError(
                'SECRET_KEY must be set to a strong value (32+ chars) in production. '
                'Set it in your environment variables or render.yaml.'
            )
        return key

    # Local development: allow a fallback
    return key or 'local-dev-only-not-for-production'


def get_database_url():
    """Get database URL - SQLite for local dev, PostgreSQL for production.

    If DATABASE_URL is set, use PostgreSQL (production).
    Otherwise, use SQLite for local development.
    """
    url = os.getenv('DATABASE_URL')
    if url:
        # Production: PostgreSQL
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url
    # Local development: SQLite
    return 'sqlite:///denove.db'


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def is_production():
    return os.getenv('FLASK_ENV', 'development') == 'production'


def is_render():
    return bool(os.getenv('RENDER') or os.getenv('RENDER_EXTERNAL_URL'))


def get_engine_options():
    if not os.getenv('DATABASE_URL'):
        return {}

    return {
        'pool_pre_ping': True,
        'pool_recycle': _env_int('DB_POOL_RECYCLE', 300),
        'pool_size': _env_int('DB_POOL_SIZE', 2 if is_render() else 5),
        'max_overflow': _env_int('DB_MAX_OVERFLOW', 2 if is_render() else 10),
        'pool_timeout': _env_int('DB_POOL_TIMEOUT', 30),
        'pool_use_lifo': True,
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        },
    }


class Config:
    # Flask
    SECRET_KEY = get_secret_key()
    PREFERRED_URL_SCHEME = 'https' if (is_render() or is_production()) else 'http'

    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', is_render() or is_production())
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # Database - SQLite for local, PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # PostgreSQL Connection Pool Settings (for production stability)
    SQLALCHEMY_ENGINE_OPTIONS = get_engine_options()

    # File Upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5242880))  # 5MB
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp'}
