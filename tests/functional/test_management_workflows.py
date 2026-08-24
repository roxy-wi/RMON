import uuid

import pytest

import app.modules.db.sql as sql
from app.modules.db.db_model import Email, Groups, Setting, User, UserGroups
from app.modules.roxy_wi_tools import Tools


@pytest.mark.functional
def test_group_crud_workflow(client, auth_headers):
    suffix = uuid.uuid4().hex
    create_response = client.post(
        '/api/v1.0/group',
        json={'name': f'group-{suffix}', 'description': 'created by functional test'},
        headers=auth_headers(1, 1),
    )
    assert create_response.status_code == 201
    group_id = create_response.get_json()['id']

    get_response = client.get(
        f'/api/v1.0/group/{group_id}', headers=auth_headers(1, 1)
    )
    assert get_response.status_code == 200
    assert get_response.get_json()['name'] == f'group-{suffix}'
    assert Setting.select().where(Setting.group_id == group_id).count() > 0

    update_response = client.put(
        f'/api/v1.0/group/{group_id}',
        json={'name': f'updated-{suffix}', 'description': 'updated description'},
        headers=auth_headers(1, 1),
    )
    assert update_response.status_code == 201
    assert Groups.get_by_id(group_id).name == f'updated-{suffix}'

    delete_response = client.delete(
        f'/api/v1.0/group/{group_id}', headers=auth_headers(1, 1)
    )
    assert delete_response.status_code == 204
    assert not Groups.select().where(Groups.group_id == group_id).exists()
    assert not Setting.select().where(Setting.group_id == group_id).exists()


@pytest.mark.functional
def test_user_crud_and_search_workflow(client, auth_headers):
    suffix = uuid.uuid4().hex
    payload = {
        'username': f'managed-{suffix}',
        'password': 'Managed-Password-123!',
        'email': f'managed-{suffix}@example.test',
        'enabled': True,
        'group_id': 1,
        'role': 3,
    }
    create_response = client.post(
        '/api/v1.0/user', json=payload, headers=auth_headers(1, 1)
    )
    assert create_response.status_code == 201
    user_id = create_response.get_json()['id']

    get_response = client.get(
        f'/api/v1.0/user/{user_id}', headers=auth_headers(1, 1)
    )
    assert get_response.status_code == 200
    assert get_response.get_json()[0]['user_id']['username'] == payload['username']
    assert 'password' not in get_response.get_json()[0]['user_id']

    updated_username = f'updated-{suffix}'
    update_response = client.put(
        f'/api/v1.0/user/{user_id}',
        json={
            'username': updated_username,
            'email': f'updated-{suffix}@example.test',
            'enabled': False,
        },
        headers=auth_headers(1, 1),
    )
    assert update_response.status_code == 201

    search_response = client.get(
        f'/api/v1.0/users?username={updated_username}', headers=auth_headers(1, 1)
    )
    assert search_response.status_code == 200
    assert [user['username'] for user in search_response.get_json()] == [updated_username]
    assert search_response.get_json()[0]['enabled'] == 0

    delete_response = client.delete(
        f'/api/v1.0/user/{user_id}', headers=auth_headers(1, 1)
    )
    assert delete_response.status_code == 204
    assert not User.select().where(User.user_id == user_id).exists()


@pytest.mark.functional
def test_user_group_membership_workflow(client, auth_headers):
    suffix = uuid.uuid4().hex
    group = Groups.create(name=f'membership-{suffix}', description='membership test')
    user = User.create(
        username=f'member-{suffix}',
        email=f'member-{suffix}@example.test',
        password=Tools.get_hash('Membership-Password-123!'),
        role='3',
        group_id=1,
        enabled=1,
    )
    UserGroups.create(user_id=user.user_id, user_group_id=1, user_role_id=3)

    add_response = client.post(
        f'/api/v1.0/user/{user.user_id}/groups/{group.group_id}',
        json={'role_id': 4},
        headers=auth_headers(1, 1),
    )
    assert add_response.status_code == 201

    list_response = client.get(
        f'/api/v1.0/user/{user.user_id}/groups', headers=auth_headers(1, 1)
    )
    assert list_response.status_code == 200
    memberships = {
        membership['user_group_id']['group_id']: membership['user_role_id']
        for membership in list_response.get_json()
    }
    assert memberships[group.group_id] == 4

    delete_response = client.delete(
        f'/api/v1.0/user/{user.user_id}/groups/{group.group_id}',
        headers=auth_headers(1, 1),
    )
    assert delete_response.status_code == 204
    assert not UserGroups.select().where(
        (UserGroups.user_id == user.user_id)
        & (UserGroups.user_group_id == group.group_id)
    ).exists()


@pytest.mark.functional
def test_settings_read_update_and_restore_workflow(client, auth_headers):
    original_value = sql.get_setting('session_ttl', group_id=1)
    try:
        update_response = client.post(
            '/api/v1.0/settings/main',
            json={'param': 'session_ttl', 'value': '9'},
            headers=auth_headers(2, 1),
        )
        assert update_response.status_code == 201

        get_response = client.get(
            '/api/v1.0/settings/main', headers=auth_headers(2, 1)
        )
        assert get_response.status_code == 200
        settings = {setting['param']: setting['value'] for setting in get_response.get_json()}
        assert settings['session_ttl'] == '9'
    finally:
        sql.update_setting('session_ttl', str(original_value), 1)


@pytest.mark.functional
def test_email_channel_crud_workflow(client, auth_headers):
    suffix = uuid.uuid4().hex
    payload = {
        'token': f'alerts-{suffix}@example.test',
        'channel_name': f'email-{suffix}',
        'group_id': 1,
    }
    create_response = client.post(
        '/api/v1.0/channel/email', json=payload, headers=auth_headers(2, 1)
    )
    assert create_response.status_code == 201
    channel_id = create_response.get_json()['id']

    get_response = client.get(
        f'/api/v1.0/channel/email/{channel_id}', headers=auth_headers(2, 1)
    )
    assert get_response.status_code == 200
    assert get_response.get_json()['token'] == payload['token']

    updated_payload = {
        'token': f'updated-{suffix}@example.test',
        'channel_name': f'updated-email-{suffix}',
        'group_id': 1,
    }
    update_response = client.put(
        f'/api/v1.0/channel/email/{channel_id}',
        json=updated_payload,
        headers=auth_headers(2, 1),
    )
    assert update_response.status_code == 201

    list_response = client.get(
        '/api/v1.0/channels/email', headers=auth_headers(2, 1)
    )
    assert list_response.status_code == 200
    assert updated_payload['channel_name'] in {
        channel['channel_name'] for channel in list_response.get_json()
    }

    delete_response = client.delete(
        f'/api/v1.0/channel/email/{channel_id}', headers=auth_headers(2, 1)
    )
    assert delete_response.status_code == 204
    assert not Email.select().where(Email.id == channel_id).exists()
