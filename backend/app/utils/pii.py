"""Encryption for personal identifiers (national ID numbers).

Keys
----
* PII_ENCRYPTION_KEY (recommended): a dedicated Fernet key, independent of
  SECRET_KEY, so the session secret can be rotated without losing ID numbers.
* Legacy key: derived from SECRET_KEY. Every value written before the
  dedicated key existed uses it, so it is always kept as a decryption key.

New values are encrypted with the dedicated key when it is set, otherwise
with the legacy key. `flask pii-reencrypt` rewrites stored values under the
current primary key once a dedicated key has been configured.
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from flask import current_app

logger = logging.getLogger(__name__)

FERNET_TOKEN_PREFIX = 'gAAAAA'


def _config_value(name):
    try:
        return current_app.config.get(name)
    except RuntimeError:
        if name == 'SECRET_KEY':
            from app.config import get_secret_key

            return get_secret_key()
        import os

        return os.getenv(name)


def _legacy_key():
    secret = _config_value('SECRET_KEY') or 'local-dev-only-not-for-production'
    digest = hashlib.sha256(secret.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def _keys():
    keys = []
    dedicated = (_config_value('PII_ENCRYPTION_KEY') or '').strip()
    if dedicated:
        try:
            keys.append(Fernet(dedicated.encode('utf-8')))
        except (ValueError, TypeError) as exc:
            raise RuntimeError(
                'PII_ENCRYPTION_KEY is not a valid Fernet key. Generate one with: '
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            ) from exc
    keys.append(Fernet(_legacy_key()))
    return keys


def _cipher():
    return MultiFernet(_keys())


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
        if token.startswith(FERNET_TOKEN_PREFIX):
            # Encrypted with a key we no longer have. Never show the ciphertext
            # as if it were the ID number.
            logger.warning('Could not decrypt a stored ID number; check PII_ENCRYPTION_KEY / SECRET_KEY.')
            return None
        # Legacy plaintext that was never encrypted.
        return token


def reencrypt_value(value):
    """Re-encrypt an existing token under the current primary key."""
    token = str(value or '').strip()
    if not token:
        return None
    try:
        return _cipher().rotate(token.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        return None
