import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

import app.modules.tools.smon_agent as agents
import app.routes.smon.agent_routes as routes
import app.modules.roxywi.overview as overview
from app.modules.server.ssh_connection import SshConnection
from app.modules.db.db_model import Server, SmonAgent


@pytest.fixture
def agent():
    server = Server.create(hostname='health-test', ip=f'{uuid.uuid4().hex}.test', group_id='1')
    row = SmonAgent.create(server_id=server, name='Health test', uuid=str(uuid.uuid4()), description='', port=5101)
    yield row
    row.delete_instance()
    server.delete_instance()


@pytest.mark.parametrize('running', [True, False])
def test_health_uses_dedicated_probe(monkeypatch, running):
    get = Mock(return_value=json.dumps({'status': 'ok', 'running': running}).encode())
    monkeypatch.setattr(agents, 'send_get_request_to_agent', get)
    assert agents.get_agent_health(7, '192.0.2.10')['running'] is running
    get.assert_called_once_with(7, '192.0.2.10', 'health')


def http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(response=response)


def test_old_agent_can_use_scheduler_status(monkeypatch):
    get = Mock(side_effect=[http_error(404), b'{"running": true}'])
    monkeypatch.setattr(agents, 'send_get_request_to_agent', get)
    assert agents.get_agent_health(7, 'host') == {'running': True}
    assert [call.args[2] for call in get.call_args_list] == ['health', 'scheduler']


@pytest.mark.parametrize('status', [401, 403, 500])
def test_health_does_not_hide_auth_or_server_errors(monkeypatch, status):
    get = Mock(side_effect=http_error(status))
    monkeypatch.setattr(agents, 'send_get_request_to_agent', get)
    with pytest.raises(requests.HTTPError):
        agents.get_agent_health(7, 'host')
    assert get.call_count == 1


@pytest.mark.parametrize('payload', [b'<!doctype html>', b'{}', b'[]', b'{"running":"true"}'])
def test_health_rejects_invalid_responses(monkeypatch, payload):
    monkeypatch.setattr(agents, 'send_get_request_to_agent', Mock(return_value=payload))
    with pytest.raises(ValueError):
        agents.get_agent_health(7, 'host')


@pytest.mark.parametrize('status', [200, 404, 500])
def test_agent_transport_checks_http_status_and_closes(monkeypatch, status):
    response = Mock(content=b'ok')
    if status != 200:
        response.raise_for_status.side_effect = http_error(status)
    monkeypatch.setattr(agents.requests, 'get', Mock(return_value=response))
    monkeypatch.setattr(agents, 'get_agent_headers', lambda _: {})
    monkeypatch.setattr(agents.smon_sql, 'get_agent_data', lambda _: SimpleNamespace(port=5101))
    monkeypatch.setattr(agents.smon_sql, 'get_agent_ip_by_id', lambda _: '127.0.0.1')
    if status == 200:
        assert agents.send_get_request_to_agent(1, 'host', 'health') == b'ok'
    else:
        with pytest.raises(requests.HTTPError):
            agents.send_get_request_to_agent(1, 'host', 'health')
    response.raise_for_status.assert_called_once()
    response.close.assert_called_once()


@pytest.mark.parametrize('endpoint,payload,expected', [
    ('status', b'{"running":true}', {'running': True}),
    ('uptime', b'{"uptime":"2026-09-07 06:00:00"}', {'uptime': '2026-09-07 06:00:00'}),
    ('checks', b'0', 0),
    ('version', b'{"version":"1.20"}', {'version': '1.20'}),
])
def test_agent_probes_return_json(client, auth_headers, agent, monkeypatch, endpoint, payload, expected):
    monkeypatch.setattr(agents, 'send_get_request_to_agent', Mock(return_value=payload))
    response = client.get(f'/rmon/agent/{endpoint}/{agent.server_id.ip}?agent_id={agent.id}', headers=auth_headers(1, 1))
    assert response.status_code == 200
    assert response.is_json
    assert response.get_json() == expected


@pytest.mark.parametrize('endpoint', ['status', 'uptime', 'checks', 'version'])
def test_html_upstream_is_json_failure_not_success(client, auth_headers, agent, monkeypatch, endpoint):
    monkeypatch.setattr(agents, 'send_get_request_to_agent', Mock(return_value=b'<!doctype html><h1>404</h1>'))
    response = client.get(f'/rmon/agent/{endpoint}/{agent.server_id.ip}?agent_id={agent.id}', headers=auth_headers(1, 1))
    assert response.status_code == 502
    assert response.is_json and 'error' in response.get_json()
    assert '<!doctype' not in response.get_data(as_text=True)


@pytest.mark.parametrize('action', ['start', 'stop', 'restart'])
@pytest.mark.parametrize('loopback', [True, False])
def test_service_actions_always_use_ssh(client, auth_headers, agent, monkeypatch, action, loopback):
    if loopback:
        agent.server_id.ip = '127.0.0.1'
        agent.server_id.save()
    ssh = Mock(return_value='')
    monkeypatch.setattr(routes.server_mod, 'ssh_command', ssh)
    response = client.post(f'/rmon/agent/action/{action}', data={'agent_id': agent.id}, headers=auth_headers(1, 1))
    assert response.status_code == 200 and response.get_json() == {'status': 'ok'}
    ssh.assert_called_once_with(agent.server_id.ip, f'sudo systemctl {action} rmon-agent', timeout=30, rc=True)


def test_service_ssh_errors_have_json_failure_status(client, auth_headers, agent, monkeypatch):
    monkeypatch.setattr(routes.server_mod, 'ssh_command', Mock(side_effect=ValueError('SSH credentials are not configured for this server')))
    response = client.post('/rmon/agent/action/start', data={'agent_id': agent.id}, headers=auth_headers(1, 1))
    assert response.status_code == 502
    assert 'SSH credentials' in response.get_json()['error']


def test_missing_ssh_credentials_are_not_a_key_error():
    with pytest.raises(ValueError, match='SSH credentials are not configured'):
        SshConnection('127.0.0.1', {'port': 22})


def test_probes_and_actions_enforce_agent_access(client, auth_headers, agent, monkeypatch):
    request = Mock()
    ssh = Mock()
    monkeypatch.setattr(agents, 'send_get_request_to_agent', request)
    monkeypatch.setattr(routes.server_mod, 'ssh_command', ssh)
    response = client.get(f'/rmon/agent/status/another.test?agent_id={agent.id}', headers=auth_headers(1, 1))
    assert response.status_code == 403
    response = client.post('/rmon/agent/action/start', data={'agent_id': agent.id}, headers=auth_headers(3, 1))
    assert response.status_code == 403
    request.assert_not_called()
    ssh.assert_not_called()


@pytest.mark.parametrize('available', [True, False])
def test_overview_uses_same_health_probe(monkeypatch, available):
    monkeypatch.setattr(overview.roxywi_common, 'get_jwt_token_claims', lambda: {'user_id': 1, 'group': '1'})
    monkeypatch.setattr(overview.roxywi_common, 'get_user_lang_for_flask', lambda: 'en')
    monkeypatch.setattr(overview.user_sql, 'get_role_id', lambda *_: 1)
    monkeypatch.setattr(overview.server_sql, 'get_server_by_ip', lambda _: SimpleNamespace(hostname='agent'))
    monkeypatch.setattr(overview.smon_sql, 'get_agent_id_by_ip', lambda _: 7)
    probe = Mock(return_value={'running': True})
    if not available:
        probe.side_effect = requests.ConnectionError()
    monkeypatch.setattr(agents, 'get_agent_health', probe)
    monkeypatch.setattr(overview, 'render_template', lambda _, **kwargs: kwargs)
    context = overview.show_overview('127.0.0.1')
    probe.assert_called_once_with(7, '127.0.0.1')
    assert context['service_status'][3]['running'] is available
