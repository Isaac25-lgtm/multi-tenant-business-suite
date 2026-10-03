"""Shared test setup.

Unit tests need nothing extra. Integration tests run against a real
PostgreSQL database named in TEST_DATABASE_URL; they are skipped when it is
not set. The database is wiped, so it must be a dedicated test database.

    TEST_DATABASE_URL=postgresql://postgres:<password>@localhost:5432/denove_aps_test
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TEST_DATABASE_URL = os.getenv('TEST_DATABASE_URL', '').strip()


@pytest.fixture
def db_app():
    if not TEST_DATABASE_URL:
        pytest.skip('TEST_DATABASE_URL is not set; skipping PostgreSQL integration tests.')
    database_name = TEST_DATABASE_URL.rsplit('/', 1)[-1].split('?', 1)[0]
    if 'test' not in database_name.lower():
        pytest.exit(f'Refusing to wipe "{database_name}": TEST_DATABASE_URL must name a test database.')

    from app import create_app
    from app.config import Config, normalize_postgres_url
    from app.extensions import db

    class TestConfig(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = normalize_postgres_url(TEST_DATABASE_URL)
        SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
        MONTHLY_ACCRUAL_TIMING = 'arrears'

    app = create_app(TestConfig)
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(db_app):
    return db_app.test_client()


@pytest.fixture
def make_user(db_app):
    from app.extensions import db
    from app.models.user import User

    def _make(username='manager', role='manager', **extra):
        user = User(username=username, role=role, is_active=True, **extra)
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        return user

    return _make


@pytest.fixture
def login(client):
    """Put a user into the test client's session as if they had signed in."""
    def _login(user, section=None, **session_values):
        with client.session_transaction() as sess:
            sess['user_id'] = user.id
            sess['username'] = user.username
            sess['section'] = section or user.role
            sess.update(session_values)
    return _login
