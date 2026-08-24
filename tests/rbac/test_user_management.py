import uuid

import pytest

from app.modules.db.db_model import Groups, User, UserGroups


def _user_payload(group_id: int, role: int) -> dict:
    suffix = uuid.uuid4().hex
    return {
        'username': f'user-{suffix}',
        'password': 'TestPassword-123!',
        'email': f'{suffix}@example.test',
        'enabled': True,
        'group_id': group_id,
        'role': role,
    }


@pytest.mark.rbac
def test_superadmin_can_create_user_in_any_group(client, auth_headers):
    foreign_group = Groups.create(name=f'user-group-{uuid.uuid4().hex}', description='user RBAC test')
    payload = _user_payload(foreign_group.group_id, role=2)

    response = client.post('/api/v1.0/user', json=payload, headers=auth_headers(1, 1))

    assert response.status_code == 201
    user = User.get(User.username == payload['username'])
    membership = UserGroups.get(
        (UserGroups.user_id == user.user_id)
        & (UserGroups.user_group_id == foreign_group.group_id)
    )
    assert membership.user_role_id == 2


@pytest.mark.rbac
def test_group_admin_cannot_create_superadmin_or_cross_tenants(client, auth_headers):
    foreign_group = Groups.create(name=f'forbidden-{uuid.uuid4().hex}', description='user RBAC denial test')
    superadmin_payload = _user_payload(1, role=1)
    foreign_payload = _user_payload(foreign_group.group_id, role=2)

    superadmin_response = client.post(
        '/api/v1.0/user', json=superadmin_payload, headers=auth_headers(2, 1)
    )
    foreign_response = client.post(
        '/api/v1.0/user', json=foreign_payload, headers=auth_headers(2, 1)
    )

    assert superadmin_response.status_code != 201
    assert foreign_response.status_code != 201
    assert not User.select().where(
        User.username.in_([superadmin_payload['username'], foreign_payload['username']])
    ).exists()
