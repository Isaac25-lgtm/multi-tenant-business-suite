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
    return 'sqlite:///denove.db'


class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database - SQLite for local, PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # PostgreSQL Connection Pool Settings (for production stability)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Check connection health before using
        'pool_recycle': 300,    # Recycle connections every 5 minutes
        'pool_size': 5,         # Number of connections to maintain
        'max_overflow': 10,     # Max connections beyond pool_size
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        } if os.getenv('DATABASE_URL') else {}  # Only for PostgreSQL
    }

    # File Upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5242880))  # 5MB
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}
