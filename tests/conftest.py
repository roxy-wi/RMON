import os
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = Path(tempfile.mkdtemp(prefix='rmon-tests-'))
PROJECT_RUNTIME_DIR = PROJECT_ROOT / 'tests' / '.runtime'

for directory in (
    PROJECT_RUNTIME_DIR / 'log',
    PROJECT_RUNTIME_DIR / 'lib' / 'keys',
    RUNTIME_DIR / 'prometheus',
):
    directory.mkdir(parents=True, exist_ok=True)

os.environ.update({
    'RMON_TESTING': '1',
    'RMON_CONFIG_FILE': str(PROJECT_ROOT / 'tests' / 'fixtures' / 'rmon.cfg'),
    'RMON_DB_PATH': str(RUNTIME_DIR / 'rmon.db'),
    'RMON_PROMETHEUS_MULTIPROC_DIR': str(RUNTIME_DIR / 'prometheus'),
    'RMON_SECRET_KEY': 'test-only-flask-secret-key-with-at-least-32-chars',
    'RMON_JWT_ALGORITHM': 'HS256',
    'RMON_JWT_SECRET_KEY': 'test-only-jwt-secret-key-with-at-least-32-chars',
    'RMON_SECRET_PHRASE': 'E2nCq8NnECvPQ5zUQntL_-Nt-qBncYkrEmMkYGzVpyM=',
    'RMON_COOKIE_SECURE': '0',
})


import pytest
from flask_jwt_extended import create_access_token

from app import app as flask_app
from app import create_db
from app.modules.db.db_model import create_tables


create_tables()
create_db.default_values()


@pytest.fixture(scope='session')
def app():
    flask_app.config.update(TESTING=True, JWT_COOKIE_SECURE=False, SESSION_COOKIE_SECURE=False)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(app):
    def make_headers(user_id: int, group_id: int) -> dict:
        with app.app_context():
            token = create_access_token(str(user_id), additional_claims={'group': str(group_id)})
        return {'Authorization': f'Bearer {token}'}

    return make_headers
