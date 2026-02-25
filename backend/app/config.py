import os
from dotenv import load_dotenv

load_dotenv()


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
    return 'sqlite:///devs.db'


class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database - SQLite for local, PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Database engine options - PostgreSQL pool settings for production only
    if os.getenv('DATABASE_URL'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 5,
            'max_overflow': 10,
            'connect_args': {
                'connect_timeout': 10,
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5,
            }
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {}

    # File Upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5242880))  # 5MB
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}
