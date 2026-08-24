import uuid

import pytest

from app.modules.db.db_model import User, UserGroups
from app.modules.roxy_wi_tools import Tools


def _create_login_user(*, enabled: bool = True) -> tuple[User, str]:
    suffix = uuid.uuid4().hex
    password = f'Functional-{suffix}!'
    user = User.create(
        username=f'login-{suffix}',
        email=f'login-{suffix}@example.test',
        password=Tools.get_hash(password),
        role='2',
        group_id=1,
        enabled=int(enabled),
    )
    UserGroups.create(user_id=user.user_id, user_group_id=1, user_role_id=2)
    return user, password


@pytest.mark.functional
def test_api_login_token_authorizes_follow_up_requests(client):
    user, password = _create_login_user()

    login_response = client.post(
        '/api/v1.0/login', json={'login': user.username, 'password': password}
    )

    assert login_response.status_code == 200
    token = login_response.get_json()['access_token']
    assert token.count('.') == 2

    servers_response = client.get(
        '/api/v1.0/servers', headers={'Authorization': f'Bearer {token}'}
    )
    assert servers_response.status_code == 200
    assert servers_response.is_json


@pytest.mark.functional
def test_web_login_sets_cookie_and_rejects_external_next_url(client, monkeypatch):
    user, password = _create_login_user()
    monkeypatch.setattr('app.login.roxy.update_plan', lambda: None)

    response = client.post(
        '/login',
        json={'login': user.username, 'pass': password, 'next': 'https://attacker.example/path'},
    )

    assert response.status_code == 200
    assert response.get_json()['next_url'] == 'https://localhost/overview'
    assert 'access_token_cookie=' in response.headers['Set-Cookie']

    cookie_authenticated_response = client.get('/api/v1.0/servers')
    assert cookie_authenticated_response.status_code == 200


@pytest.mark.functional
@pytest.mark.parametrize('enabled, password_is_correct', [(True, False), (False, True)])
def test_login_rejects_wrong_password_and_disabled_accounts(client, enabled, password_is_correct):
    user, password = _create_login_user(enabled=enabled)
    supplied_password = password if password_is_correct else 'definitely-wrong'

    response = client.post(
        '/api/v1.0/login', json={'login': user.username, 'password': supplied_password}
    )

    assert response.status_code == 401
    assert 'access_token' not in response.get_json()
