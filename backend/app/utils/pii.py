import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _secret_material():
    try:
        secret = current_app.config.get('SECRET_KEY')
    except RuntimeError:
        from app.config import get_secret_key

        secret = get_secret_key()

    secret = secret or 'local-dev-only-not-for-production'
    digest = hashlib.sha256(secret.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def _cipher():
    return Fernet(_secret_material())


def encrypt_value(value):
    normalized = str(value or '').strip()
    if not normalized:
        return None
    return _cipher().encrypt(normalized.encode('utf-8')).decode('utf-8')


def decrypt_value(value):
    token = str(value or '').strip()
    if not token:
        return None
    try:
        return _cipher().decrypt(token.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        return token
