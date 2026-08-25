import json
import importlib
import time
import uuid
from pathlib import Path
from urllib.error import URLError

import pytest
from authlib.jose import JsonWebKey, JsonWebToken
from flask import render_template
from pydantic import ValidationError
from peewee import OperationalError

from app.modules.db.db_model import (
    Groups,
    OidcGroupMapping,
    OidcIdentity,
    OidcProvider,
    Role,
    User,
    UserGroups,
)
from app.modules.oidc.errors import OidcLoginError
from app.modules.oidc.login import complete_oidc_login, extract_claim, normalize_groups
from app.modules.oidc.schemas import OidcProviderCreate
from app.modules.roxy_wi_tools import Tools
from app.modules.server.ssh import crypt_password
from app.routes.oidc import routes as oidc_routes


SUPPORTED_LANGUAGES = ('en', 'fr', 'pt-br', 'ru')


def make_provider(**overrides):
    suffix = uuid.uuid4().hex
    values = {
        'slug': f'oidc-test-{suffix}',
        'label': 'Test OIDC',
        'enabled': 1,
        'client_id': 'rmon-test',
        'metadata_url': None,
        'issuer': 'https://idp.example.test',
        'authorization_endpoint': 'https://idp.example.test/authorize',
        'token_endpoint': 'https://idp.example.test/token',
        'userinfo_endpoint': 'https://idp.example.test/userinfo',
        'jwks_uri': 'https://idp.example.test/jwks',
        'scope': 'openid email profile',
        'subject_claim': 'sub',
        'email_claim': 'email',
        'username_claim': 'preferred_username',
        'groups_claim': 'groups',
        'allowed_domains': json.dumps([]),
        'auto_create_users': 0,
        'auto_link_by_email': 1,
        'require_verified_email': 1,
        'sync_group_memberships': 1,
        'remove_missing_group_memberships': 0,
        'default_group_id': 1,
        'default_role_id': 4,
    }
    values.update(overrides)
    return OidcProvider.create(**values)


def oidc_claims(subject='subject', **overrides):
    claims = {
        'iss': 'https://idp.example.test',
        'sub': subject,
        'email': f'oidc-test-{uuid.uuid4().hex}@example.test',
        'email_verified': True,
        'preferred_username': f'oidc-test-{uuid.uuid4().hex}',
        'groups': [],
    }
    claims.update(overrides)
    return claims


@pytest.fixture(autouse=True)
def clean_oidc_data():
    OidcGroupMapping.delete().execute()
    OidcIdentity.delete().execute()
    OidcProvider.delete().execute()
    yield
    OidcGroupMapping.delete().execute()
    OidcIdentity.delete().execute()
    user_ids = [
        user.user_id
        for user in User.select(User.user_id).where(User.username.startswith('oidc-test-'))
    ]
    if user_ids:
        UserGroups.delete().where(UserGroups.user_id.in_(user_ids)).execute()
        User.delete().where(User.user_id.in_(user_ids)).execute()
    OidcProvider.delete().execute()
    Groups.delete().where(Groups.name.startswith('OIDC Test ')).execute()


@pytest.fixture(autouse=True)
def silence_oidc_logs(monkeypatch):
    monkeypatch.setattr(oidc_routes.roxywi_common, 'logging_without_user', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('app.routes.admin.oidc_routes.roxywi_common.logger', lambda *_args, **_kwargs: None)


def create_group():
    return Groups.create(name=f'OIDC Test {uuid.uuid4().hex}', description='OIDC test group')


def signed_token(provider, key, nonce='expected-nonce', **claim_overrides):
    now = int(time.time())
    claims = {
        'iss': provider.issuer,
        'sub': 'stable-subject',
        'aud': provider.client_id,
        'exp': now + 300,
        'iat': now,
        'nonce': nonce,
    }
    claims.update(claim_overrides)
    return JsonWebToken(['RS256']).encode(
        {'alg': 'RS256', 'kid': 'test-key'}, claims, key
    )


@pytest.mark.security
def test_oidc_public_provider_list_and_login_page_hide_disabled(client):
    enabled = make_provider(label='Company Login')
    make_provider(label='Disabled Login', enabled=0)

    response = client.get('/oidc/providers')
    assert response.status_code == 200
    assert response.get_json() == [{'label': 'Company Login', 'slug': enabled.slug}]

    login_page = client.get('/login').get_data(as_text=True)
    assert 'Sign in with Company Login' in login_page
    assert f'/oidc/{enabled.slug}/login' in login_page
    assert 'Disabled Login' not in login_page


@pytest.mark.security
def test_local_login_remains_available_before_oidc_migration(client, monkeypatch):
    monkeypatch.setattr(
        'app.login.oidc_sql.list_providers',
        lambda **_kwargs: (_ for _ in ()).throw(OperationalError('no such table')),
    )
    response = client.get('/login')
    assert response.status_code == 200
    assert 'id="login-form"' in response.get_data(as_text=True)


@pytest.mark.security
def test_oidc_disabled_or_unknown_provider_cannot_start_login(client):
    disabled = make_provider(enabled=0)
    assert client.get(f'/oidc/{disabled.slug}/login').status_code == 404
    assert client.get('/oidc/not-configured/login').status_code == 404


@pytest.mark.security
def test_oidc_login_stores_state_nonce_callback_and_safe_return_path(client, monkeypatch, app):
    provider = make_provider(userinfo_endpoint=None)
    app.config['PUBLIC_URL'] = 'https://rmon.example.test/'

    class FakeOAuthSession:
        def __init__(self, **kwargs):
            assert kwargs['client_id'] == provider.client_id
            assert kwargs['redirect_uri'] == f'https://rmon.example.test/oidc/{provider.slug}/callback'

        @staticmethod
        def create_authorization_url(endpoint, nonce):
            assert endpoint == provider.authorization_endpoint
            assert nonce
            return 'https://idp.example.test/authorize?state=generated-state', 'generated-state'

    monkeypatch.setattr(oidc_routes, 'OAuth2Session', FakeOAuthSession)
    response = client.get(f'/oidc/{provider.slug}/login?next=/admin')
    assert response.status_code == 302
    assert response.location.startswith('https://idp.example.test/authorize')
    with client.session_transaction() as oidc_session:
        assert oidc_session[f'oidc_state:{provider.slug}'] == 'generated-state'
        assert oidc_session[f'oidc_nonce:{provider.slug}']
        assert oidc_session[f'oidc_return_to:{provider.slug}'] == '/admin'
    app.config['PUBLIC_URL'] = ''


@pytest.mark.security
@pytest.mark.parametrize('unsafe_next', ('https://evil.test/', '//evil.test/', '/\\evil.test/', 'admin'))
def test_oidc_login_rejects_external_or_malformed_return_path(client, monkeypatch, unsafe_next):
    provider = make_provider()

    class FakeOAuthSession:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def create_authorization_url(_endpoint, nonce):
            return f'https://idp.example.test/authorize?nonce={nonce}', 'state'

    monkeypatch.setattr(oidc_routes, 'OAuth2Session', FakeOAuthSession)
    client.get(f'/oidc/{provider.slug}/login', query_string={'next': unsafe_next})
    with client.session_transaction() as oidc_session:
        assert oidc_session[f'oidc_return_to:{provider.slug}'] == '/overview'


@pytest.mark.security
def test_oidc_login_requires_authorization_endpoint(client):
    provider = make_provider(authorization_endpoint=None)
    response = client.get(f'/oidc/{provider.slug}/login')
    assert response.status_code == 400
    assert response.get_json()['error'] == 'oidc_not_configured'


@pytest.mark.security
def test_oidc_callback_rejects_and_consumes_wrong_state(client):
    provider = make_provider()
    with client.session_transaction() as oidc_session:
        oidc_session[f'oidc_state:{provider.slug}'] = 'expected-state'
        oidc_session[f'oidc_nonce:{provider.slug}'] = 'expected-nonce'

    first = client.get(f'/oidc/{provider.slug}/callback?code=code&state=wrong-state')
    second = client.get(f'/oidc/{provider.slug}/callback?code=code&state=expected-state')
    assert first.status_code == second.status_code == 400
    assert first.get_json()['error'] == second.get_json()['error'] == 'oidc_state_invalid'


@pytest.mark.security
def test_oidc_callback_reports_provider_authorization_error(client):
    provider = make_provider()
    with client.session_transaction() as oidc_session:
        oidc_session[f'oidc_state:{provider.slug}'] = 'expected-state'
        oidc_session[f'oidc_nonce:{provider.slug}'] = 'expected-nonce'
    response = client.get(
        f'/oidc/{provider.slug}/callback?error=access_denied&error_description=User+cancelled'
        '&state=expected-state'
    )
    assert response.status_code == 400
    assert response.get_json() == {
        'status': 'failed', 'error': 'oidc_authorization_error', 'message': 'User cancelled'
    }
    with client.session_transaction() as oidc_session:
        assert f'oidc_state:{provider.slug}' not in oidc_session


@pytest.mark.security
def test_oidc_callback_issues_normal_jwt_cookie_and_sanitizes_redirect(client, monkeypatch):
    provider = make_provider(userinfo_endpoint=None)

    class FakeOAuthSession:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def fetch_token(endpoint, authorization_response, timeout):
            assert endpoint == provider.token_endpoint
            assert 'state=expected-state' in authorization_response
            assert timeout == 10
            return {'id_token': 'signed-token', 'access_token': 'access-token'}

    monkeypatch.setattr(oidc_routes, 'OAuth2Session', FakeOAuthSession)
    monkeypatch.setattr(oidc_routes, '_validate_id_token', lambda *_args, **_kwargs: {'sub': 'subject'})
    monkeypatch.setattr(oidc_routes, '_fetch_userinfo', lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        oidc_routes, 'complete_oidc_login',
        lambda *_args, **_kwargs: {'group': '1', 'user': 1, 'name': 'admin'},
    )
    with client.session_transaction() as oidc_session:
        oidc_session[f'oidc_state:{provider.slug}'] = 'expected-state'
        oidc_session[f'oidc_nonce:{provider.slug}'] = 'expected-nonce'
        oidc_session[f'oidc_return_to:{provider.slug}'] = 'https://evil.example/'

    response = client.get(f'/oidc/{provider.slug}/callback?code=code&state=expected-state')
    assert response.status_code == 302
    assert response.location == '/overview'
    assert any('access_token_cookie=' in cookie for cookie in response.headers.getlist('Set-Cookie'))


@pytest.mark.security
def test_oidc_callback_requires_token_endpoint(client, monkeypatch):
    provider = make_provider(token_endpoint=None)
    with client.session_transaction() as oidc_session:
        oidc_session[f'oidc_state:{provider.slug}'] = 'state'
        oidc_session[f'oidc_nonce:{provider.slug}'] = 'nonce'
    response = client.get(f'/oidc/{provider.slug}/callback?code=code&state=state')
    assert response.status_code == 400
    assert response.get_json()['error'] == 'oidc_not_configured'


@pytest.mark.security
def test_oidc_signed_id_token_is_verified(monkeypatch):
    provider = make_provider()
    key = JsonWebKey.generate_key('RSA', 2048, is_private=True, options={'kid': 'test-key'})
    monkeypatch.setattr(
        oidc_routes, '_load_jwks', lambda *_args: {'keys': [key.as_dict(is_private=False)]}
    )
    claims = oidc_routes._validate_id_token(
        provider,
        {'id_token_signing_alg_values_supported': ['RS256']},
        {'id_token': signed_token(provider, key)},
        'expected-nonce',
    )
    assert claims['sub'] == 'stable-subject'


@pytest.mark.security
@pytest.mark.parametrize(
    ('claim_overrides', 'nonce'),
    (
        ({'iss': 'https://wrong-issuer.test'}, 'expected-nonce'),
        ({'aud': 'wrong-client'}, 'expected-nonce'),
        ({'exp': 1}, 'expected-nonce'),
        ({}, 'wrong-expected-nonce'),
    ),
)
def test_oidc_id_token_rejects_invalid_security_claims(monkeypatch, claim_overrides, nonce):
    provider = make_provider()
    key = JsonWebKey.generate_key('RSA', 2048, is_private=True, options={'kid': 'test-key'})
    monkeypatch.setattr(
        oidc_routes, '_load_jwks', lambda *_args: {'keys': [key.as_dict(is_private=False)]}
    )
    with pytest.raises(OidcLoginError) as error:
        oidc_routes._validate_id_token(
            provider,
            {'id_token_signing_alg_values_supported': ['RS256']},
            {'id_token': signed_token(provider, key, **claim_overrides)},
            nonce,
        )
    assert error.value.error == 'oidc_id_token_invalid'


@pytest.mark.security
@pytest.mark.parametrize(
    ('metadata', 'token', 'nonce', 'expected_error'),
    (
        ({}, {}, 'nonce', 'oidc_id_token_missing'),
        ({}, {'id_token': 'token'}, '', 'oidc_nonce_missing'),
        ({'id_token_signing_alg_values_supported': ['none']}, {'id_token': 'token'}, 'nonce', 'oidc_alg_missing'),
    ),
)
def test_oidc_id_token_rejects_missing_inputs(metadata, token, nonce, expected_error):
    provider = make_provider()
    with pytest.raises(OidcLoginError) as error:
        oidc_routes._validate_id_token(provider, metadata, token, nonce)
    assert error.value.error == expected_error


@pytest.mark.security
def test_oidc_userinfo_subject_must_match_signed_token():
    with pytest.raises(OidcLoginError) as error:
        oidc_routes._merge_claims(
            {'sub': 'signed-subject', 'email': 'signed@example.test'},
            {'sub': 'different-subject', 'email': 'userinfo@example.test'},
        )
    assert error.value.error == 'oidc_subject_mismatch'
    merged = oidc_routes._merge_claims(
        {'sub': 'same-subject', 'email': 'signed@example.test'},
        {'sub': 'same-subject', 'email': 'userinfo@example.test', 'name': 'Name'},
    )
    assert merged['email'] == 'signed@example.test'
    assert merged['name'] == 'Name'


@pytest.mark.security
def test_oidc_userinfo_uses_decrypted_client_secret(monkeypatch):
    provider = make_provider(client_secret_encrypted=crypt_password('client-secret').decode('ascii'))

    class FakeResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {'sub': 'subject', 'email': 'user@example.test'}

    class FakeOAuthSession:
        def __init__(self, **kwargs):
            assert kwargs['client_secret'] == 'client-secret'
            assert kwargs['token'] == {'access_token': 'token'}

        @staticmethod
        def get(endpoint, timeout):
            assert endpoint == provider.userinfo_endpoint
            assert timeout == 10
            return FakeResponse()

    monkeypatch.setattr(oidc_routes, 'OAuth2Session', FakeOAuthSession)
    assert oidc_routes._fetch_userinfo(provider, {}, {'access_token': 'token'})['sub'] == 'subject'


@pytest.mark.security
def test_oidc_userinfo_failure_is_sanitized(monkeypatch):
    provider = make_provider()

    class FailingOAuthSession:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def get(_endpoint, timeout):
            assert timeout == 10
            raise RuntimeError('sensitive upstream detail')

    monkeypatch.setattr(oidc_routes, 'OAuth2Session', FailingOAuthSession)
    with pytest.raises(OidcLoginError) as error:
        oidc_routes._fetch_userinfo(provider, {}, {'access_token': 'token'})
    assert error.value.error == 'oidc_userinfo_failed'
    assert 'sensitive' not in error.value.message


@pytest.mark.security
@pytest.mark.parametrize(
    'body', (b'not-json', b'[]', b'x' * (1024 * 1024 + 1)),
    ids=('invalid-json', 'not-an-object', 'too-large'),
)
def test_oidc_metadata_loader_rejects_invalid_or_oversized_json(monkeypatch, body):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _size):
            return body

    monkeypatch.setattr(oidc_routes, 'urlopen', lambda *_args, **_kwargs: FakeResponse())
    with pytest.raises(OidcLoginError) as error:
        oidc_routes._load_json_url('https://idp.test/metadata', 'metadata_error', 'failed')
    assert error.value.error == 'metadata_error'
    assert error.value.status_code == 502


@pytest.mark.security
def test_oidc_metadata_loader_sanitizes_network_failures(monkeypatch):
    monkeypatch.setattr(
        oidc_routes, 'urlopen', lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError('private DNS detail')),
    )
    with pytest.raises(OidcLoginError) as error:
        oidc_routes._load_json_url('https://idp.test/metadata', 'metadata_error', 'Could not load metadata')
    assert error.value.error == 'metadata_error'
    assert error.value.message == 'Could not load metadata'


@pytest.mark.security
def test_oidc_metadata_discovery_supplies_endpoints(client, monkeypatch):
    provider = make_provider(
        metadata_url='https://idp.example.test/.well-known/openid-configuration',
        authorization_endpoint=None,
    )
    monkeypatch.setattr(
        oidc_routes, '_load_metadata',
        lambda _provider: {'authorization_endpoint': 'https://discovered.test/authorize'},
    )

    class FakeOAuthSession:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def create_authorization_url(endpoint, nonce):
            assert endpoint == 'https://discovered.test/authorize'
            return f'{endpoint}?nonce={nonce}', 'state'

    monkeypatch.setattr(oidc_routes, 'OAuth2Session', FakeOAuthSession)
    assert client.get(f'/oidc/{provider.slug}/login').status_code == 302


@pytest.mark.security
def test_oidc_callback_unexpected_failure_returns_generic_error(client, monkeypatch):
    provider = make_provider()

    class FailingOAuthSession:
        def __init__(self, **_kwargs):
            pass

        @staticmethod
        def fetch_token(*_args, **_kwargs):
            raise RuntimeError('sensitive token endpoint detail')

    monkeypatch.setattr(oidc_routes, 'OAuth2Session', FailingOAuthSession)
    with client.session_transaction() as oidc_session:
        oidc_session[f'oidc_state:{provider.slug}'] = 'expected-state'
        oidc_session[f'oidc_nonce:{provider.slug}'] = 'expected-nonce'
    response = client.get(f'/oidc/{provider.slug}/callback?code=code&state=expected-state')
    assert response.status_code == 502
    assert response.get_json()['error'] == 'oidc_callback_failed'
    assert 'sensitive' not in response.get_data(as_text=True)


@pytest.mark.security
def test_oidc_auto_creates_user_default_membership_and_stable_identity():
    provider = make_provider(auto_create_users=1)
    claims = oidc_claims('new-user-subject', preferred_username='OIDC Test Created')
    first = complete_oidc_login(provider, claims)
    first_login_at = OidcIdentity.get(OidcIdentity.subject == 'new-user-subject').last_login_at
    second = complete_oidc_login(provider, {**claims, 'preferred_username': 'changed-name'})

    user = User.get_by_id(first['user'])
    identity = OidcIdentity.get(OidcIdentity.subject == 'new-user-subject')
    membership = UserGroups.get(
        (UserGroups.user_id == user.user_id)
        & (UserGroups.user_group_id == provider.default_group_id)
    )
    assert first['user'] == second['user'] == identity.user_id
    assert membership.user_role_id == provider.default_role_id
    assert identity.username == 'changed-name'
    assert identity.last_login_at >= first_login_at
    assert user.username == 'oidc-test-created'
    assert Tools.check_password('not-the-generated-password', user.password) == (False, False)


@pytest.mark.security
def test_oidc_links_existing_verified_user_by_case_insensitive_email():
    provider = make_provider(auto_create_users=0, auto_link_by_email=1)
    suffix = uuid.uuid4().hex
    user = User.create(
        username=f'oidc-test-linked-{suffix}', email=f'OIDC-Test-{suffix}@Example.Test',
        password=Tools.get_hash('Local-password-only!'), role='3', group_id=1, enabled=1,
    )
    UserGroups.create(user_id=user.user_id, user_group_id=1, user_role_id=3)
    result = complete_oidc_login(provider, oidc_claims(
        'linked-subject', email=user.email.lower(), preferred_username='external-name'
    ))
    assert result['user'] == user.user_id
    assert OidcIdentity.get(OidcIdentity.subject == 'linked-subject').user_id == user.user_id


@pytest.mark.security
def test_oidc_rejects_existing_email_when_auto_link_is_disabled():
    provider = make_provider(auto_create_users=1, auto_link_by_email=0)
    user = User.create(
        username=f'oidc-test-collision-{uuid.uuid4().hex}',
        email=f'oidc-test-collision-{uuid.uuid4().hex}@example.test',
        password=Tools.get_hash('local'), role='4', group_id=1, enabled=1,
    )
    with pytest.raises(OidcLoginError) as error:
        complete_oidc_login(provider, oidc_claims('collision-subject', email=user.email))
    assert error.value.error == 'oidc_email_already_exists'


@pytest.mark.security
def test_oidc_rejects_disabled_linked_user():
    provider = make_provider(auto_create_users=0, auto_link_by_email=1)
    user = User.create(
        username=f'oidc-test-disabled-{uuid.uuid4().hex}',
        email=f'oidc-test-disabled-{uuid.uuid4().hex}@example.test',
        password=Tools.get_hash('local'), role='4', group_id=1, enabled=0,
    )
    with pytest.raises(OidcLoginError) as error:
        complete_oidc_login(provider, oidc_claims('disabled-subject', email=user.email))
    assert error.value.error == 'oidc_user_disabled'


@pytest.mark.security
@pytest.mark.parametrize(
    ('provider_overrides', 'claims', 'expected_error'),
    (
        ({'auto_create_users': 1}, {'email': 'user@example.test'}, 'oidc_subject_missing'),
        ({'auto_create_users': 1, 'issuer': None}, {'sub': 'subject', 'iss': None, 'email': 'user@example.test'}, 'oidc_issuer_missing'),
        ({'auto_create_users': 0}, {'sub': 'unknown', 'email': 'unknown@example.test'}, 'oidc_user_not_found'),
    ),
)
def test_oidc_identity_resolution_requires_subject_issuer_and_known_user(
    provider_overrides, claims, expected_error
):
    provider = make_provider(**provider_overrides)
    complete_claims = {'email_verified': True, 'preferred_username': 'oidc-test-resolution'}
    complete_claims.update(claims)
    with pytest.raises(OidcLoginError) as error:
        complete_oidc_login(provider, complete_claims)
    assert error.value.error == expected_error


@pytest.mark.security
def test_oidc_group_mapping_supports_dotted_claim_casefold_and_active_group():
    group = create_group()
    provider = make_provider(auto_create_users=1, groups_claim='realm_access.roles')
    OidcGroupMapping.create(
        provider_id=provider.id, external_group='rmon-editors', group_id=group.group_id,
        role_id=2, active=1, priority=10,
    )
    result = complete_oidc_login(provider, oidc_claims(
        'mapped-subject', realm_access={'roles': ['RMON-EDITORS']}
    ))
    user = User.get_by_id(result['user'])
    membership = UserGroups.get(
        (UserGroups.user_id == user.user_id) & (UserGroups.user_group_id == group.group_id)
    )
    assert user.group_id.group_id == group.group_id
    assert membership.user_role_id == 2
    assert extract_claim({'realm_access': {'roles': ['one']}}, 'realm_access.roles') == ['one']


@pytest.mark.security
def test_oidc_group_mapping_priority_selects_first_active_group():
    first_group = create_group()
    second_group = create_group()
    provider = make_provider(auto_create_users=1)
    OidcGroupMapping.create(
        provider_id=provider.id, external_group='second', group_id=second_group.group_id,
        role_id=4, priority=20,
    )
    OidcGroupMapping.create(
        provider_id=provider.id, external_group='first', group_id=first_group.group_id,
        role_id=2, priority=10,
    )
    result = complete_oidc_login(provider, oidc_claims(
        'priority-subject', groups=['SECOND', 'FIRST']
    ))
    assert result['group'] == str(first_group.group_id)
    memberships = {
        item.user_group_id.group_id: item.user_role_id
        for item in UserGroups.select().where(UserGroups.user_id == result['user'])
    }
    assert memberships == {first_group.group_id: 2, second_group.group_id: 4}


@pytest.mark.security
def test_oidc_removes_mapped_membership_missing_from_later_claims():
    first_group = create_group()
    second_group = create_group()
    provider = make_provider(auto_create_users=1, remove_missing_group_memberships=1)
    for external, group in (('first', first_group), ('second', second_group)):
        OidcGroupMapping.create(
            provider_id=provider.id, external_group=external, group_id=group.group_id,
            role_id=4, priority=10,
        )
    claims = oidc_claims('sync-subject', groups=['first', 'second'])
    result = complete_oidc_login(provider, claims)
    complete_oidc_login(provider, {**claims, 'groups': ['second']})
    memberships = {
        item.user_group_id.group_id
        for item in UserGroups.select().where(UserGroups.user_id == result['user'])
    }
    assert memberships == {second_group.group_id}
    assert User.get_by_id(result['user']).group_id.group_id == second_group.group_id


@pytest.mark.security
def test_oidc_unmatched_group_rolls_back_new_user_and_identity():
    group = create_group()
    provider = make_provider(auto_create_users=1)
    OidcGroupMapping.create(
        provider_id=provider.id, external_group='required-group', group_id=group.group_id, role_id=4,
    )
    email = f'oidc-test-orphan-{uuid.uuid4().hex}@example.test'
    with pytest.raises(OidcLoginError) as error:
        complete_oidc_login(provider, oidc_claims(
            'orphan-subject', email=email, groups=['another-group']
        ))
    assert error.value.error == 'oidc_group_mapping_not_matched'
    assert User.get_or_none(User.email == email) is None
    assert OidcIdentity.get_or_none(OidcIdentity.subject == 'orphan-subject') is None


@pytest.mark.security
@pytest.mark.parametrize(
    ('claims_update', 'expected_error'),
    (
        ({'email': 'user@evil.test'}, 'oidc_domain_denied'),
        ({'email_verified': False}, 'oidc_email_not_verified'),
        ({'email': None}, 'oidc_domain_denied'),
    ),
)
def test_oidc_email_policy_rejections(claims_update, expected_error):
    provider = make_provider(auto_create_users=1, allowed_domains=json.dumps(['example.test']))
    with pytest.raises(OidcLoginError) as error:
        complete_oidc_login(provider, oidc_claims('policy-subject', **claims_update))
    assert error.value.error == expected_error


@pytest.mark.security
def test_oidc_requires_email_to_create_user_even_when_verification_is_optional():
    provider = make_provider(auto_create_users=1, require_verified_email=0)
    with pytest.raises(OidcLoginError) as error:
        complete_oidc_login(provider, oidc_claims('missing-email', email=None))
    assert error.value.error == 'oidc_email_missing'


@pytest.mark.security
def test_oidc_username_is_sanitized_and_made_unique():
    provider = make_provider(auto_create_users=1)
    first = complete_oidc_login(provider, oidc_claims(
        'username-one', preferred_username='  Name With Spaces!  '
    ))
    second = complete_oidc_login(provider, oidc_claims(
        'username-two', preferred_username='Name With Spaces!'
    ))
    assert User.get_by_id(first['user']).username == 'name-with-spaces'
    assert User.get_by_id(second['user']).username == 'name-with-spaces-2'


@pytest.mark.security
@pytest.mark.parametrize(
    ('value', 'expected'),
    (
        (None, []), ('one,two', ['one', 'two']), ('["one", "two"]', ['one', 'two']),
        (['one', 2, ''], ['one', '2']), (42, ['42']),
    ),
)
def test_oidc_group_claim_normalization(value, expected):
    assert normalize_groups(value) == expected


@pytest.mark.security
@pytest.mark.parametrize(
    'payload',
    (
        {'slug': 'Uppercase', 'label': 'Valid label', 'client_id': 'client', 'metadata_url': 'https://idp.test'},
        {'slug': 'valid', 'label': 'Valid label', 'client_id': 'client', 'metadata_url': 'file:///etc/passwd'},
        {'slug': 'valid', 'label': 'Valid label', 'client_id': 'client', 'metadata_url': 'https://idp.test', 'scope': 'email profile'},
        {'slug': 'valid', 'label': 'Valid label', 'client_id': 'client', 'metadata_url': 'https://idp.test', 'allowed_domains': ['user@example.test']},
    ),
)
def test_oidc_provider_schema_rejects_unsafe_configuration(payload):
    with pytest.raises(ValidationError):
        OidcProviderCreate.model_validate(payload)


@pytest.mark.security
def test_oidc_admin_api_requires_superadmin(client, auth_headers):
    anonymous = client.get('/admin/oidc/providers')
    assert anonymous.status_code == 302
    assert '/login' in anonymous.location
    assert client.get('/admin/oidc/providers', headers=auth_headers(2, 1)).status_code == 403
    assert client.get('/admin/oidc/providers', headers=auth_headers(1, 1)).status_code == 200


@pytest.mark.security
def test_oidc_admin_api_encrypts_secret_and_keeps_it_on_empty_update(client, auth_headers):
    headers = auth_headers(1, 1)
    payload = {
        'slug': f'admin-{uuid.uuid4().hex}', 'label': 'Admin OIDC', 'client_id': 'rmon',
        'client_secret': 'super-secret-value',
        'metadata_url': 'https://idp.example.test/.well-known/openid-configuration',
        'default_group_id': 1, 'default_role_id': 4,
    }
    response = client.post('/admin/oidc/providers', json=payload, headers=headers)
    assert response.status_code == 201, response.get_data(as_text=True)
    data = response.get_json()
    assert data['client_secret_configured'] is True
    assert 'client_secret' not in data and 'client_secret_encrypted' not in data
    assert data['callback_url'].endswith(f'/oidc/{payload["slug"]}/callback')

    provider = OidcProvider.get_by_id(data['id'])
    original_secret = provider.client_secret_encrypted
    assert original_secret != payload['client_secret']
    response = client.put(
        f'/admin/oidc/providers/{provider.id}', json={'client_secret': ''}, headers=headers,
    )
    assert response.status_code == 200
    assert OidcProvider.get_by_id(provider.id).client_secret_encrypted == original_secret


@pytest.mark.security
def test_oidc_admin_api_rejects_incomplete_enabled_provider(client, auth_headers):
    response = client.post('/admin/oidc/providers', headers=auth_headers(1, 1), json={
        'slug': f'incomplete-{uuid.uuid4().hex}', 'label': 'Incomplete', 'client_id': 'client',
    })
    assert response.status_code == 400
    assert 'metadata_url or these fields' in response.get_json()['error']


@pytest.mark.security
def test_oidc_admin_api_returns_structured_validation_and_duplicate_errors(client, auth_headers):
    headers = auth_headers(1, 1)
    invalid = client.post('/admin/oidc/providers', headers=headers, json={
        'slug': 'UPPERCASE', 'label': 'x', 'client_id': '', 'metadata_url': 'file:///etc/passwd',
    })
    assert invalid.status_code == 400
    assert invalid.get_json()['error'] == 'validation_error'
    assert {detail['field'] for detail in invalid.get_json()['details']} >= {
        'slug', 'label', 'client_id', 'metadata_url'
    }

    provider = make_provider(slug=f'duplicate-{uuid.uuid4().hex}')
    duplicate = client.post('/admin/oidc/providers', headers=headers, json={
        'slug': provider.slug, 'label': 'Duplicate provider', 'client_id': 'client',
        'metadata_url': 'https://idp.example.test/.well-known/openid-configuration',
    })
    assert duplicate.status_code == 409


@pytest.mark.security
def test_oidc_admin_api_returns_not_found_and_invalid_target_errors(client, auth_headers):
    headers = auth_headers(1, 1)
    assert client.put('/admin/oidc/providers/999999', json={}, headers=headers).status_code == 404
    assert client.get('/admin/oidc/providers/999999/mappings', headers=headers).status_code == 404
    provider = make_provider()
    invalid_target = client.post(
        f'/admin/oidc/providers/{provider.id}/mappings', headers=headers,
        json={'external_group': 'admins', 'group_id': 999999, 'role_id': 4},
    )
    assert invalid_target.status_code == 400
    assert 'group does not exist' in invalid_target.get_json()['error']


@pytest.mark.security
def test_oidc_admin_mapping_crud_duplicate_and_validation(client, auth_headers):
    headers = auth_headers(1, 1)
    group = create_group()
    provider = make_provider()
    payload = {'external_group': 'external-admins', 'group_id': group.group_id, 'role_id': 2, 'priority': 5}

    created = client.post(
        f'/admin/oidc/providers/{provider.id}/mappings', json=payload, headers=headers,
    )
    assert created.status_code == 201
    mapping = created.get_json()
    assert mapping['group_name'] == group.name and mapping['role_name'] == 'admin'
    assert client.post(
        f'/admin/oidc/providers/{provider.id}/mappings', json=payload, headers=headers,
    ).status_code == 409

    updated_payload = {**payload, 'external_group': 'external-editors', 'role_id': 3, 'active': False}
    updated = client.put(
        f'/admin/oidc/mappings/{mapping["id"]}', json=updated_payload, headers=headers,
    )
    assert updated.status_code == 200
    assert updated.get_json()['active'] is False
    listed = client.get(
        f'/admin/oidc/providers/{provider.id}/mappings', headers=headers,
    ).get_json()
    assert [item['external_group'] for item in listed] == ['external-editors']
    assert client.delete(f'/admin/oidc/mappings/{mapping["id"]}', headers=headers).get_json() == {'status': 'Ok'}
    assert client.delete(f'/admin/oidc/mappings/{mapping["id"]}', headers=headers).status_code == 404


@pytest.mark.security
def test_oidc_identity_and_mapping_are_cleaned_up_with_parent_records(monkeypatch):
    from app.modules.db import group as group_sql
    from app.modules.db import user as user_sql

    group = create_group()
    provider = make_provider(auto_create_users=1)
    result = complete_oidc_login(provider, oidc_claims('cleanup-subject'))
    identity_id = OidcIdentity.get(OidcIdentity.subject == 'cleanup-subject').id
    mapping = OidcGroupMapping.create(
        provider_id=provider.id, external_group='cleanup', group_id=group.group_id, role_id=4,
    )
    monkeypatch.setattr(user_sql, 'out_error', lambda exc: pytest.fail(str(exc)))
    monkeypatch.setattr(group_sql, 'out_error', lambda exc: pytest.fail(str(exc)))

    assert user_sql.delete_user(result['user']) is True
    assert OidcIdentity.get_or_none(OidcIdentity.id == identity_id) is None
    group_sql.delete_group(group.group_id)
    assert OidcGroupMapping.get_or_none(OidcGroupMapping.id == mapping.id) is None


@pytest.mark.security
def test_oidc_admin_ui_and_translation_catalogs_are_complete(app):
    with app.test_request_context('/admin'):
        catalogs = {
            language: app.jinja_env.get_template(f'languages/{language}.html').module.oidc_page
            for language in SUPPORTED_LANGUAGES
        }
        html = render_template(
            'include/admin_oidc.html', groups=list(Groups.select()), roles=list(Role.select()),
            lang=app.jinja_env.get_template('languages/en.html').module,
        )
    expected_keys = set(catalogs['en'])
    assert expected_keys
    assert all(set(catalog) == expected_keys for catalog in catalogs.values())
    assert all(value.strip() for catalog in catalogs.values() for value in catalog.values())
    for element_id in (
        'oidc-provider-form', 'oidc-provider-dialog', 'oidc-mapping-form',
        'oidc-mapping-dialog', 'oidc-mappings-dialog',
    ):
        assert f'id="{element_id}"' in html


@pytest.mark.security
def test_oidc_ui_assets_have_menu_anchor_and_no_duplicate_icon_builder(app):
    app_root = Path(app.root_path)
    script = (app_root / 'static' / 'js' / 'admin' / 'oidc.js').read_text(encoding='utf-8')
    menu = (app_root / 'templates' / 'include' / 'main_menu.html').read_text(encoding='utf-8')
    assert "append($('<i>')" not in script
    assert "url_for('admin.admin') }}#oidc" in menu
    assert 'class="oidc head-submenu"' in menu


@pytest.mark.security
def test_oidc_migration_creates_and_drops_all_tables(monkeypatch):
    migration = importlib.import_module('app.migrations.20260824030000_add_oidc')

    class FakeDatabase:
        created = None
        dropped = None

        def create_tables(self, models, safe):
            self.created = (models, safe)

        def drop_tables(self, models, safe):
            self.dropped = (models, safe)

    database = FakeDatabase()
    monkeypatch.setattr(migration, 'connect', lambda: database)
    migration.upgrade()
    migration.downgrade()
    assert database.created == ([OidcProvider, OidcIdentity, OidcGroupMapping], True)
    assert database.dropped == ([OidcGroupMapping, OidcIdentity, OidcProvider], True)
