import uuid

import pytest
from flask import g

import app.modules.db.group as group_sql
import app.modules.roxywi.common as roxywi_common
from app.modules.db.db_model import Groups, Server, SmonAgent
from app.modules.roxywi.exception import RoxywiGroupMismatch


@pytest.mark.rbac
def test_superadmin_sees_every_group_and_regular_admin_sees_memberships(app):
    foreign_group = Groups.create(name=f'visible-{uuid.uuid4().hex}', description='visibility test')

    with app.test_request_context('/'):
        g.user_params = {'user_id': 1, 'group_id': '1', 'role': 1}
        superadmin_group_ids = {group.group_id for group in roxywi_common.get_visible_groups()}

    with app.test_request_context('/'):
        g.user_params = {'user_id': 2, 'group_id': '1', 'role': 2}
        admin_group_ids = {group.group_id for group in roxywi_common.get_visible_groups()}

    assert foreign_group.group_id in superadmin_group_ids
    assert foreign_group.group_id not in admin_group_ids
    assert admin_group_ids == {1}


@pytest.mark.rbac
def test_superadmin_groups_api_returns_all_groups(client, auth_headers):
    foreign_group = Groups.create(name=f'api-visible-{uuid.uuid4().hex}', description='API visibility test')

    response = client.get('/api/v1.0/groups', headers=auth_headers(1, 1))

    assert response.status_code == 200
    assert foreign_group.group_id in {group['group_id'] for group in response.get_json()}


@pytest.mark.rbac
def test_global_server_access_is_reserved_for_role_one(app):
    with app.test_request_context('/'):
        g.user_params = {'user_id': 1, 'group_id': '1', 'role': 1}
        roxywi_common.require_active_group_access(999)

    with app.test_request_context('/'):
        g.user_params = {'user_id': 2, 'group_id': '1', 'role': 2}
        with pytest.raises(RoxywiGroupMismatch):
            roxywi_common.require_active_group_access(999)


@pytest.mark.rbac
def test_server_api_allows_superadmin_but_denies_foreign_group_admin(client, auth_headers):
    foreign_group = Groups.create(name=f'server-{uuid.uuid4().hex}', description='server tenant test')
    foreign_server = Server.create(
        hostname=f'foreign-{uuid.uuid4().hex}', ip=f'198.51.100.{foreign_group.group_id % 200 + 1}',
        group_id=str(foreign_group.group_id), enabled=1, cred_id=1, port=22, description='foreign server'
    )

    superadmin_response = client.get(
        f'/api/v1.0/server/{foreign_server.server_id}?group_id={foreign_group.group_id}',
        headers=auth_headers(1, 1),
    )
    admin_response = client.get(
        f'/api/v1.0/server/{foreign_server.server_id}',
        headers=auth_headers(2, 1),
    )

    assert superadmin_response.status_code == 200
    assert admin_response.status_code in {403, 404}


@pytest.mark.rbac
def test_agent_api_allows_superadmin_but_denies_foreign_group_admin(client, auth_headers):
    foreign_group = Groups.create(name=f'agent-{uuid.uuid4().hex}', description='agent tenant test')
    foreign_server = Server.create(
        hostname=f'agent-host-{uuid.uuid4().hex}', ip=f'203.0.113.{foreign_group.group_id % 200 + 1}',
        group_id=str(foreign_group.group_id), enabled=1, cred_id=1, port=22, description='agent host'
    )
    agent = SmonAgent.create(
        server_id=foreign_server.server_id, name=f'agent-{uuid.uuid4().hex}', uuid=str(uuid.uuid4()),
        enabled=1, description='agent', shared=0, port=5101
    )

    superadmin_response = client.get(
        f'/api/v1.0/rmon/agent/{agent.id}', headers=auth_headers(1, 1)
    )
    admin_response = client.get(
        f'/api/v1.0/rmon/agent/{agent.id}', headers=auth_headers(2, 1)
    )

    assert superadmin_response.status_code == 200
    assert 'uuid' not in superadmin_response.get_json()
    assert admin_response.status_code in {403, 404}
