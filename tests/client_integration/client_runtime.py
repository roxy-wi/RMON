"""Opt-in contract tests against an independent result processor checkout."""
import os
from pathlib import Path
import sys

import pytest

root = os.getenv('RMON_TEST_SERVER_ROOT')
if not root:
    pytest.skip('Set RMON_TEST_SERVER_ROOT to run cross-component client contracts', allow_module_level=True)
root = Path(root).resolve()
if not (root / 'modules/client_telemetry/wsgi.py').is_file():
    raise RuntimeError('RMON_TEST_SERVER_ROOT must contain the client collector implementation')
sys.path.insert(0, str(root))

# Use only the disposable database configured by tests/conftest.py.
backend = os.getenv('RMON_TEST_DATABASE', 'sqlite')
os.environ.pop('RMON_DATABASE_URL_FILE', None)
os.environ['RMON_DATABASE_URL'] = {
    'sqlite': 'sqlite:///' + os.environ['RMON_DB_PATH'],
    'postgres': 'postgresql://rmon_test:rmon-test-only@127.0.0.1:5432/rmon_client_test',
    'mysql': 'mysql://rmon_test:rmon-test-only@127.0.0.1:3306/rmon_client_test',
}[backend]
from modules.db import connection as server_connection
