from types import SimpleNamespace

import pytest

import app.modules.server.server as server_mod
import app.modules.tools.smon_agent as smon_agent


@pytest.mark.security
def test_ssh_passphrase_is_sent_over_stdin_not_embedded_in_shell(monkeypatch):
    captured = {}

    class Process:
        returncode = 0

        def communicate(self, value):
            captured['stdin'] = value
            return '', ''

    def popen(command, **kwargs):
        captured['command'] = command
        captured['kwargs'] = kwargs
        return Process()

    monkeypatch.setattr(server_mod.subprocess, 'Popen', popen)
    passphrase = 'legacy;$(touch /tmp/should-not-run)'

    server_mod.add_key_to_agent(
        {'passphrase': passphrase, 'key': '/tmp/key with spaces'},
        {'pid': '123', 'socket': '/tmp/agent.sock'},
    )

    assert passphrase not in captured['command']
    assert captured['stdin'] == f'{passphrase}\n'
    assert captured['kwargs']['env']['SSH_AGENT_PID'] == '123'


@pytest.mark.security
def test_agent_http_request_ignores_caller_supplied_host(monkeypatch):
    captured = {}

    def get(url, **kwargs):
        captured['url'] = url
        captured['kwargs'] = kwargs
        return SimpleNamespace(content=b'ok')

    monkeypatch.setattr(smon_agent, 'get_agent_headers', lambda _agent_id: {'Agent-UUID': 'uuid'})
    monkeypatch.setattr(smon_agent.smon_sql, 'get_agent_data', lambda _agent_id: SimpleNamespace(port=5101))
    monkeypatch.setattr(smon_agent.smon_sql, 'get_agent_ip_by_id', lambda _agent_id: '192.0.2.10')
    monkeypatch.setattr(smon_agent.requests, 'get', get)

    result = smon_agent.send_get_request_to_agent(1, '169.254.169.254', 'version')

    assert result == b'ok'
    assert captured['url'] == 'http://192.0.2.10:5101/version'
    assert captured['kwargs']['timeout'] == 5
