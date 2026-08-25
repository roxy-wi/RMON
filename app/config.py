import os
import secrets
from datetime import timedelta
from pathlib import Path


def _load_secret_key():
    secret_key = os.getenv('RMON_SECRET_KEY')
    if secret_key:
        if len(secret_key) < 32:
            raise RuntimeError('RMON_SECRET_KEY must contain at least 32 characters')
        return secret_key

    secret_file = Path(os.getenv('RMON_SECRET_KEY_FILE', '/var/lib/rmon/keys/flask-secret'))
    try:
        secret_key = secret_file.read_text(encoding='utf-8').strip()
    except FileNotFoundError:
        secret_file.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        secret_key = secrets.token_urlsafe(48)
        try:
            descriptor = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            secret_key = secret_file.read_text(encoding='utf-8').strip()
        else:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
                file.write(secret_key)

    if len(secret_key) < 32:
        raise RuntimeError(f'Flask secret in {secret_file} must contain at least 32 characters')
    return secret_key


def _load_jwt_configuration():
    algorithm = os.getenv('RMON_JWT_ALGORITHM', 'RS256')
    if algorithm not in {'RS256', 'HS256'}:
        raise RuntimeError('RMON_JWT_ALGORITHM must be RS256 or HS256')
    if algorithm == 'HS256':
        secret_key = os.getenv('RMON_JWT_SECRET_KEY')
        if not secret_key or len(secret_key) < 32:
            raise RuntimeError('RMON_JWT_SECRET_KEY must contain at least 32 characters')
        return algorithm, None, None, secret_key

    private_key_file = os.getenv('RMON_JWT_PRIVATE_KEY_FILE', '/var/lib/rmon/keys/rmon-key')
    public_key_file = os.getenv('RMON_JWT_PUBLIC_KEY_FILE', '/var/lib/rmon/keys/rmon-key.pub')
    with open(private_key_file, encoding='utf-8') as file:
        private_key = file.read()
    with open(public_key_file, encoding='utf-8') as file:
        public_key = file.read()
    return algorithm, private_key, public_key, None


_JWT_ALGORITHM, _JWT_PRIVATE_KEY, _JWT_PUBLIC_KEY, _JWT_SECRET_KEY = _load_jwt_configuration()


class Configuration(object):
    SECRET_KEY = _load_secret_key()
    TESTING = os.getenv('RMON_TESTING') == '1'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.getenv('RMON_COOKIE_SECURE', '1') == '1'
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 3000
    SCHEDULER_API_ENABLED = False
    SCHEDULER_ENABLED = os.getenv('RMON_SCHEDULER_ENABLED', '1') == '1'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=int(os.getenv('RMON_JWT_EXPIRES_HOURS', '1')))
    JWT_ALGORITHM = _JWT_ALGORITHM
    JWT_PRIVATE_KEY = _JWT_PRIVATE_KEY
    JWT_PUBLIC_KEY = _JWT_PUBLIC_KEY
    JWT_SECRET_KEY = _JWT_SECRET_KEY
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_SECURE = SESSION_COOKIE_SECURE
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_IDENTITY_CLAIM = 'user_id'
    JWT_ERROR_MESSAGE_KEY = 'error'
    FLASK_PYDANTIC_VALIDATION_ERROR_RAISE = True
    MAX_CONTENT_LENGTH = int(os.getenv('RMON_MAX_CONTENT_LENGTH', str(16 * 1024 * 1024)))
    MAX_FORM_MEMORY_SIZE = int(os.getenv('RMON_MAX_FORM_MEMORY_SIZE', str(2 * 1024 * 1024)))
    PUBLIC_URL = os.getenv('RMON_PUBLIC_URL', '').rstrip('/')
    JSONIFY_PRETTYPRINT_REGULAR = False
