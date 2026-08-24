from types import SimpleNamespace
import uuid

import pytest

import app.modules.server.server as server_mod
from app.modules.db.db_model import Cred, Server


@pytest.mark.functional
def test_credential_crud_workflow(client, auth_headers):
    suffix = uuid.uuid4().hex
    payload = {
        'name': f'credential-{suffix}',
        'username': 'root',
        'password': 'Credential-Password-123!',
        'key_enabled': False,
        'group_id': 1,
        'shared': 0,
    }
    create_response = client.post(
        '/api/v1.0/server/cred', json=payload, headers=auth_headers(2, 1)
    )
    assert create_response.status_code == 200
    credential_id = create_response.get_json()['id']
    assert Cred.get_by_id(credential_id).password != payload['password']

    get_response = client.get(
        f'/api/v1.0/server/cred/{credential_id}', headers=auth_headers(2, 1)
    )
    assert get_response.status_code == 200
    assert get_response.get_json()[0]['password'] == payload['password']

    updated_payload = {
        **payload,
        'name': f'updated-credential-{suffix}',
        'username': 'deploy',
        'password': 'Updated-Credential-Password-123!',
    }
    update_response = client.put(
        f'/api/v1.0/server/cred/{credential_id}',
        json=updated_payload,
        headers=auth_headers(2, 1),
    )
    assert update_response.status_code == 201

    list_response = client.get(
        '/api/v1.0/server/creds', headers=auth_headers(2, 1)
    )
    assert list_response.status_code == 200
    listed_credential = next(
        credential for credential in list_response.get_json()
        if credential['id'] == credential_id
    )
    assert listed_credential['name'] == updated_payload['name']
    assert listed_credential['password'] == updated_payload['password']

    delete_response = client.delete(
        f'/api/v1.0/server/cred/{credential_id}', headers=auth_headers(2, 1)
    )
    assert delete_response.status_code == 204
    assert not Cred.select().where(Cred.id == credential_id).exists()


@pytest.mark.functional
def test_server_crud_workflow(client, auth_headers, monkeypatch):
    suffix = uuid.uuid4().hex
    credential = Cred.create(
        name=f'server-credential-{suffix}', username='root', password='',
        key_enabled=0, group_id=1, shared=0,
    )
    next_host = Server.select().count() + 10
    payload = {
        'hostname': f'server-{suffix}',
        'ip': f'192.0.2.{next_host}',
        'enabled': True,
        'cred_id': credential.id,
        'port': 22,
        'description': 'functional server',
        'group_id': 1,
    }
    monkeypatch.setattr(server_mod, 'update_server_after_creating', lambda *_args: None)
    monkeypatch.setattr(
        server_mod.subprocess,
        'run',
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout='', stderr=''),
    )

    create_response = client.post(
        '/api/v1.0/server', json=payload, headers=auth_headers(2, 1)
    )
    assert create_response.status_code == 201
    server_id = create_response.get_json()['id']

    get_response = client.get(
        f'/api/v1.0/server/{server_id}', headers=auth_headers(2, 1)
    )
    assert get_response.status_code == 200
    assert get_response.get_json()['ip'] == payload['ip']

    updated_payload = {
        **payload,
        'hostname': f'updated-server-{suffix}',
        'port': 2222,
        'description': 'updated functional server',
    }
    update_response = client.put(
        f'/api/v1.0/server/{server_id}',
        json=updated_payload,
        headers=auth_headers(2, 1),
    )
    assert update_response.status_code == 201

    list_response = client.get('/api/v1.0/servers', headers=auth_headers(2, 1))
    assert list_response.status_code == 200
    listed_server = next(
        server for server in list_response.get_json() if server['server_id'] == server_id
    )
    assert listed_server['hostname'] == updated_payload['hostname']
    assert listed_server['port'] == 2222

    delete_response = client.delete(
        f'/api/v1.0/server/{server_id}', headers=auth_headers(2, 1)
    )
    assert delete_response.status_code == 204
    assert not Server.select().where(Server.server_id == server_id).exists()


@pytest.mark.functional
def test_server_payload_validation_rejects_invalid_address(client, auth_headers):
    response = client.post(
        '/api/v1.0/server',
        json={
            'hostname': 'invalid-address',
            'ip': 'not a valid address',
            'enabled': True,
            'cred_id': 1,
            'port': 22,
            'group_id': 1,
        },
        headers=auth_headers(2, 1),
    )

    assert response.status_code == 400
    assert response.is_json
    assert response.get_json()['error']
