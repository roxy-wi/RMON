from datetime import timedelta
from uuid import uuid4

import pytest
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

from app.modules.db.db_model import Groups, User, UserGroups

pytestmark = pytest.mark.functional
REFRESH = '/api/v1.0/session/refresh'


@pytest.fixture
def session_user():
    group = Groups.create(name='session-' + uuid4().hex)
    user = User.create(username='session-' + uuid4().hex, email=uuid4().hex + '@example.test',
                       password='unused', group_id=1, role='4', enabled=1)
    UserGroups.create(user_id=user.user_id, user_group_id=group.group_id, user_role_id=4)
    yield user, group
    UserGroups.delete().where(UserGroups.user_id == user.user_id).execute()
    user.delete_instance()
    group.delete_instance()


def browser_token(app, client, session_user, *, expires=60, refresh=False):
    user, group = session_user
    with app.app_context():
        create = create_refresh_token if refresh else create_access_token
        token = create(str(user.user_id), additional_claims={'group': str(group.group_id)},
                       expires_delta=timedelta(seconds=expires))
        claims = decode_token(token, allow_expired=True)
    client.set_cookie('access_token_cookie', token)
    client.set_cookie('csrf_access_token', claims['csrf'])
    return token, claims


def test_active_browser_gets_another_hour_with_same_user_group_and_csrf(app, client, session_user):
    old, claims = browser_token(app, client, session_user)
    response = client.post(REFRESH, headers={'X-CSRF-TOKEN': claims['csrf']}, json={'user_id': '1', 'group': '1'})
    assert response.status_code == 200
    assert response.get_json() == {'refresh_after': 300}
    assert response.headers['Cache-Control'] == 'no-store'
    token = client.get_cookie('access_token_cookie').value
    with app.app_context():
        renewed = decode_token(token)
    assert token != old and renewed['jti'] != claims['jti']
    assert renewed['user_id'] == claims['user_id'] and renewed['group'] == claims['group']
    assert renewed['csrf'] == claims['csrf']
    assert renewed['exp'] - renewed['iat'] == 3600
    assert renewed['exp'] > claims['exp']
    assert 'HttpOnly' in response.headers.getlist('Set-Cookie')[0]
    assert token not in response.get_data(as_text=True)


@pytest.mark.parametrize('header', [None, 'incorrect'])
def test_refresh_requires_matching_csrf(app, client, session_user, header):
    token, _ = browser_token(app, client, session_user)
    response = client.post(REFRESH, headers={} if header is None else {'X-CSRF-TOKEN': header})
    assert response.status_code == 401
    assert client.get_cookie('access_token_cookie').value == token
    assert not response.headers.getlist('Set-Cookie')


def test_bearer_api_token_alone_cannot_extend_browser_session(app, client, session_user):
    token, _ = browser_token(app, client, session_user)
    client.delete_cookie('access_token_cookie')
    response = client.post(REFRESH, headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 401
    assert not response.headers.getlist('Set-Cookie')


@pytest.mark.parametrize('state,expected', [('expired', 401), ('refresh-token', 422), ('disabled', 401), ('deleted', 401), ('removed-group', 403)])
def test_invalid_or_revoked_access_cannot_be_extended(app, client, session_user, state, expected):
    _, claims = browser_token(app, client, session_user, expires=-1 if state == 'expired' else 60, refresh=state == 'refresh-token')
    user, _ = session_user
    if state == 'disabled':
        User.update(enabled=0).where(User.user_id == user.user_id).execute()
    if state in ('deleted', 'removed-group'):
        UserGroups.delete().where(UserGroups.user_id == user.user_id).execute()
    if state == 'deleted':
        user.delete_instance()
    response = client.post(REFRESH, headers={'X-CSRF-TOKEN': claims['csrf']})
    assert response.status_code == expected
    assert not response.headers.getlist('Set-Cookie')


def test_background_read_does_not_extend_token(app, client, session_user):
    token, _ = browser_token(app, client, session_user)
    response = client.get('/rmon/dashboard/data')
    assert response.status_code == 200
    assert not response.headers.getlist('Set-Cookie')
    assert client.get_cookie('access_token_cookie').value == token


def test_two_tabs_can_renew_using_the_same_csrf(app, client, session_user):
    old, claims = browser_token(app, client, session_user)
    for _ in range(2):
        # Model two requests that left with the same original cookies.
        client.set_cookie('access_token_cookie', old)
        response = client.post(REFRESH, headers={'X-CSRF-TOKEN': claims['csrf']})
        assert response.status_code == 200
    assert client.post(REFRESH, headers={'X-CSRF-TOKEN': claims['csrf']}).status_code == 200


def test_logout_clears_cookies_and_prevents_renewal(app, client, session_user):
    _, claims = browser_token(app, client, session_user)
    assert client.get('/logout').status_code == 302
    assert not client.get_cookie('access_token_cookie')
    assert client.post(REFRESH, headers={'X-CSRF-TOKEN': claims['csrf']}).status_code == 401


def test_shorter_configured_sessions_renew_before_expiry(app, client, session_user, monkeypatch):
    monkeypatch.setitem(app.config, 'JWT_ACCESS_TOKEN_EXPIRES', timedelta(seconds=40))
    _, claims = browser_token(app, client, session_user)
    assert client.post(REFRESH, headers={'X-CSRF-TOKEN': claims['csrf']}).get_json()['refresh_after'] == 10


def test_session_script_is_only_on_authenticated_pages(app, client, session_user):
    assert 'id="rmon-session"' not in client.get('/login').get_data(as_text=True)
    browser_token(app, client, session_user)
    text = client.get('/client-checks').get_data(as_text=True)
    assert 'id="rmon-session"' in text and f'data-refresh-url="{REFRESH}"' in text
