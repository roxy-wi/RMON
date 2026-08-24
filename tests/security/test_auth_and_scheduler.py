from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.security
def test_scheduler_http_api_is_disabled(app):
    assert app.config['SCHEDULER_API_ENABLED'] is False


@pytest.mark.security
def test_api_query_string_does_not_bypass_authentication(client):
    response = client.get('/definitely-missing?api=1')

    assert response.status_code == 302
    assert response.location.startswith('/login?')


@pytest.mark.security
def test_protected_api_requires_a_token(client):
    response = client.get('/api/v1.0/groups')

    assert response.status_code == 401
    assert response.is_json


@pytest.mark.security
def test_dedicated_scheduler_runner_matches_application_configuration():
    source = (PROJECT_ROOT / 'scheduler_runner.py').read_text(encoding='utf-8')

    assert "os.environ.setdefault('RMON_SCHEDULER_ENABLED', '1')" in source
    assert "from app import scheduler" in source
    assert 'threading.Event().wait()' in source
