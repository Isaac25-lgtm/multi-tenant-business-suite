import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    """Get database URL with proper format for SQLAlchemy.

    Render provides DATABASE_URL starting with 'postgres://' but SQLAlchemy 1.4+
    requires 'postgresql://' - this function handles the conversion.
    """
    url = os.getenv('DATABASE_URL', 'sqlite:///denove_aps.db')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # Database - handle Render's postgres:// vs postgresql:// issue
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # File Upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 5242880))  # 5MB
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
