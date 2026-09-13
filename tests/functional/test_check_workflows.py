import uuid
from copy import deepcopy

import pytest

import app.modules.tools.smon_agent as smon_agent
from app.modules.db.db_model import (
    MultiCheck,
    Server,
    SMON,
    SmonAgent,
    SmonDnsCheck,
    SmonHttpCheck,
    SmonPingCheck,
    SmonRabbitCheck,
    SmonSMTPCheck,
    SmonTcpCheck,
)


CHECK_CASES = {
    'http': {
        'route': 'http',
        'model': SmonHttpCheck,
        'send_method': 'send_http_checks',
        'payload': {
            'url': 'https://example.test/health',
            'method': 'GET',
            'accepted_status_codes': [200, '300-304', '4**'],
        },
        'updated': {
            'url': 'https://example.test/ready',
            'method': 'HEAD',
            'accepted_status_codes': [204],
        },
        'field': 'url',
        'expected': 'https://example.test/ready',
    },
    'tcp': {
        'route': 'tcp',
        'model': SmonTcpCheck,
        'send_method': 'send_tcp_checks',
        'payload': {'ip': 'tcp.example.test', 'port': 443},
        'updated': {'ip': 'tcp.example.test', 'port': 8443},
        'field': 'port',
        'expected': 8443,
    },
    'dns': {
        'route': 'dns',
        'model': SmonDnsCheck,
        'send_method': 'send_dns_checks',
        'payload': {
            'resolver': '1.1.1.1',
            'port': 53,
            'record_type': 'a',
            'ip': 'example.test',
        },
        'updated': {
            'resolver': '8.8.8.8',
            'port': 53,
            'record_type': 'mx',
            'ip': 'example.test',
        },
        'field': 'resolver',
        'expected': '8.8.8.8',
    },
    'ping': {
        'route': 'ping',
        'model': SmonPingCheck,
        'send_method': 'send_ping_checks',
        'payload': {
            'ip': '192.0.2.10',
            'packet_size': 56,
            'count_packets': 3,
            'use_kernel_timestamp': False,
        },
        'updated': {
            'ip': '192.0.2.11',
            'packet_size': 64,
            'count_packets': 2,
            'use_kernel_timestamp': True,
        },
        'field': 'packet_size',
        'expected': 64,
    },
    'smtp': {
        'route': 'smtp',
        'model': SmonSMTPCheck,
        'send_method': 'send_smtp_checks',
        'payload': {
            'username': 'monitor',
            'password': 'smtp-password',
            'port': 465,
            'ip': 'smtp.example.test',
            'ignore_ssl_error': False,
        },
        'updated': {
            'username': 'updated-monitor',
            'password': 'updated-smtp-password',
            'port': 587,
            'ip': 'smtp.example.test',
            'ignore_ssl_error': True,
        },
        'field': 'port',
        'expected': 587,
    },
    'rabbitmq': {
        'route': 'rabbitmq',
        'model': SmonRabbitCheck,
        'send_method': 'send_rabbit_checks',
        'payload': {
            'username': 'monitor',
            'password': 'rabbit-password',
            'port': 5672,
            'ip': 'rabbit.example.test',
            'vhost': '/',
            'ignore_ssl_error': False,
        },
        'updated': {
            'username': 'updated-monitor',
            'password': 'updated-rabbit-password',
            'port': 5671,
            'ip': 'rabbit.example.test',
            'vhost': '/monitoring',
            'ignore_ssl_error': True,
        },
        'field': 'vhost',
        'expected': '/monitoring',
    },
}


@pytest.fixture()
def check_agent():
    suffix = uuid.uuid4().hex
    server = Server.create(
        hostname=f'agent-{suffix}',
        ip=f'agent-{suffix}.example.test',
        group_id='1',
        enabled=1,
        cred_id=1,
        port=22,
        description='functional check workflow',
    )
    agent = SmonAgent.create(
        server_id=server.server_id,
        name=f'agent-{suffix}',
        uuid=str(uuid.uuid4()),
        enabled=1,
        description='functional check workflow',
        shared=0,
        port=5101,
    )

    yield agent

    multi_check_ids = {
        check.multi_check_id.id
        for check in SMON.select().where(SMON.agent_id == agent.id)
    }
    if multi_check_ids:
        MultiCheck.delete().where(MultiCheck.id.in_(multi_check_ids)).execute()
    SmonAgent.delete().where(SmonAgent.id == agent.id).execute()
    Server.delete().where(Server.server_id == server.server_id).execute()


def _payload(check_type, agent_id, suffix):
    payload = {
        'name': f'{check_type}-{suffix}',
        'description': f'{check_type} functional workflow',
        'place': 'agent',
        'entities': [agent_id],
        'check_timeout': 3,
        'enabled': True,
        'interval': 120,
        'group_id': 1,
        'retries': 2,
        'priority': 'warning',
        'threshold_timeout': 500,
    }
    payload.update(deepcopy(CHECK_CASES[check_type]['payload']))
    return payload


@pytest.mark.functional
@pytest.mark.parametrize('check_type', CHECK_CASES)
def test_check_crud_and_agent_dispatch_workflow(
    client, auth_headers, check_agent, monkeypatch, check_type
):
    case = CHECK_CASES[check_type]
    suffix = uuid.uuid4().hex
    payload = _payload(check_type, check_agent.id, suffix)
    dispatches = []

    for configured_type, configured_case in CHECK_CASES.items():
        monkeypatch.setattr(
            smon_agent,
            configured_case['send_method'],
            lambda *args, sent_type=configured_type: dispatches.append((sent_type, args)),
        )
    monkeypatch.setattr(smon_agent, 'delete_check', lambda *_args: None)

    create_response = client.post(
        f"/api/v1.0/rmon/check/{case['route']}",
        json=payload,
        headers=auth_headers(2, 1),
    )
    assert create_response.status_code == 201, create_response.get_json()
    multi_check_id = create_response.get_json()['id']

    multi_check = MultiCheck.get_by_id(multi_check_id)
    check = SMON.get(SMON.multi_check_id == multi_check_id)
    assert multi_check.name == payload['name']
    assert multi_check.entity_type == 'agent'
    assert check.agent_id.id == check_agent.id
    assert check.check_type == check_type
    assert case['model'].select().where(case['model'].smon_id == check.id).exists()
    assert dispatches == [
        (check_type, (check_agent.id, check_agent.server_id.ip, check.id))
    ]

    get_response = client.get(
        f"/api/v1.0/rmon/check/{case['route']}/{multi_check_id}",
        headers=auth_headers(2, 1),
    )
    assert get_response.status_code == 200
    returned_check = get_response.get_json()
    assert returned_check['name'] == payload['name']
    assert returned_check['place'] == 'agent'
    assert returned_check['entities'] == [check_agent.id]
    assert returned_check['checks'][0]['smon_id']['id'] == check.id

    list_response = client.get(
        f"/api/v1.0/rmon/checks/{case['route']}",
        headers=auth_headers(2, 1),
    )
    assert list_response.status_code == 200
    assert payload['name'] in {item['name'] for item in list_response.get_json()}

    updated_payload = deepcopy(payload)
    updated_payload.update(deepcopy(case['updated']))
    updated_payload['name'] = f'updated-{check_type}-{suffix}'
    updated_payload['description'] = 'updated functional workflow'
    updated_payload['enabled'] = False
    updated_payload['priority'] = 'critical'

    update_response = client.put(
        f"/api/v1.0/rmon/check/{case['route']}/{multi_check_id}",
        json=updated_payload,
        headers=auth_headers(2, 1),
    )
    assert update_response.status_code == 201, update_response.get_json()

    updated_multi_check = MultiCheck.get_by_id(multi_check_id)
    updated_specific_check = case['model'].get(case['model'].smon_id == check.id)
    assert updated_multi_check.name == updated_payload['name']
    assert updated_multi_check.description == updated_payload['description']
    assert updated_multi_check.priority == 'critical'
    assert getattr(updated_specific_check, case['field']) == case['expected']
    assert SMON.get_by_id(check.id).enabled == 0
    assert len(dispatches) == 1

    delete_response = client.delete(
        f"/api/v1.0/rmon/check/{case['route']}/{multi_check_id}",
        headers=auth_headers(2, 1),
    )
    assert delete_response.status_code == 204
    assert not MultiCheck.select().where(MultiCheck.id == multi_check_id).exists()
    assert not SMON.select().where(SMON.id == check.id).exists()
    assert not case['model'].select().where(case['model'].smon_id == check.id).exists()


@pytest.mark.functional
@pytest.mark.parametrize(
    ('check_type', 'changes'),
    [
        ('http', {'accepted_status_codes': []}),
        ('ping', {'check_timeout': 30, 'count_packets': 4, 'interval': 120}),
        ('tcp', {'entities': []}),
    ],
)
def test_invalid_check_configuration_is_rejected(
    client, auth_headers, check_agent, check_type, changes
):
    suffix = uuid.uuid4().hex
    payload = _payload(check_type, check_agent.id, suffix)
    payload.update(changes)

    response = client.post(
        f"/api/v1.0/rmon/check/{CHECK_CASES[check_type]['route']}",
        json=payload,
        headers=auth_headers(2, 1),
    )

    assert response.status_code == 400
    assert not MultiCheck.select().where(MultiCheck.name == payload['name']).exists()


@pytest.mark.functional
@pytest.mark.parametrize('policy', ['default', 'require_https', 'require_http'])
@pytest.mark.parametrize('version', ['1.20', '2.0'])
def test_http_policy_survives_crud_and_agent_resynchronization(
    client, auth_headers, check_agent, monkeypatch, policy, version
):
    payload = _payload('http', check_agent.id, uuid.uuid4().hex)
    payload['ssl_policy'] = policy
    sent = []
    monkeypatch.setattr(smon_agent, 'send_get_request_to_agent', lambda *_: ('{"version":"' + version + '"}').encode())
    monkeypatch.setattr(smon_agent, 'send_check_to_agent', lambda *args: sent.append(args[-1]))
    monkeypatch.setattr(smon_agent, 'delete_check', lambda *_: None)
    headers = auth_headers(2, 1)
    response = client.post('/api/v1.0/rmon/check/http', json=payload, headers=headers)
    assert response.status_code == 201, response.get_json()
    multi_id = response.get_json()['id']
    check = SMON.get(SMON.multi_check_id == multi_id)
    assert SmonHttpCheck.get(SmonHttpCheck.smon_id == check.id).ssl_policy == policy
    assert sent[-1]['fail_if_not_ssl'] is (policy == 'require_https')
    assert sent[-1]['fail_if_ssl'] is (policy == 'require_http')

    returned = client.get(f'/api/v1.0/rmon/check/http/{multi_id}', headers=headers).get_json()
    assert returned['ssl_policy'] == policy
    assert returned['checks'][0]['ssl_policy'] == policy
    # A restarted agent receives the same policy when requesting all enabled checks.
    smon_agent.send_http_checks(check_agent.id, check_agent.server_id.ip)
    assert sent[-1] == sent[-2]

    payload['ssl_policy'] = 'require_http' if policy != 'require_http' else 'require_https'
    updated = client.put(f'/api/v1.0/rmon/check/http/{multi_id}', json=payload, headers=headers)
    assert updated.status_code == 201, updated.get_json()
    assert SmonHttpCheck.get(SmonHttpCheck.smon_id == check.id).ssl_policy == payload['ssl_policy']
    assert sent[-1]['fail_if_not_ssl'] is (payload['ssl_policy'] == 'require_https')
    assert sent[-1]['fail_if_ssl'] is (payload['ssl_policy'] == 'require_http')


@pytest.mark.functional
def test_http_policy_defaults_for_existing_api_clients(client, auth_headers, check_agent, monkeypatch):
    payload = _payload('http', check_agent.id, uuid.uuid4().hex)
    sent = []
    monkeypatch.setattr(smon_agent, 'send_check_to_agent', lambda *args: sent.append(args[-1]))
    response = client.post('/api/v1.0/rmon/check/http', json=payload, headers=auth_headers(2, 1))
    assert response.status_code == 201, response.get_json()
    check = SMON.get(SMON.multi_check_id == response.get_json()['id'])
    assert SmonHttpCheck.get(SmonHttpCheck.smon_id == check.id).ssl_policy == 'default'
    assert sent[-1]['fail_if_not_ssl'] is False
    assert sent[-1]['fail_if_ssl'] is False


@pytest.mark.functional
@pytest.mark.parametrize('policy', ['https', 'disabled', '', None, True, 1])
def test_invalid_http_policy_is_rejected_before_saving(client, auth_headers, check_agent, policy):
    payload = _payload('http', check_agent.id, uuid.uuid4().hex)
    payload['ssl_policy'] = policy
    response = client.post('/api/v1.0/rmon/check/http', json=payload, headers=auth_headers(2, 1))
    assert response.status_code == 400
    assert not MultiCheck.select().where(MultiCheck.name == payload['name']).exists()


@pytest.mark.parametrize('version', ['1.19', 'unknown', '', '1.18.9'])
def test_unsupported_agents_do_not_receive_required_http_policy(monkeypatch, version):
    from types import SimpleNamespace
    import json
    monkeypatch.setattr(smon_agent.smon_sql, 'select_en_smon', lambda *_: [SimpleNamespace(ssl_policy='require_https')])
    monkeypatch.setattr(smon_agent, 'send_get_request_to_agent', lambda *_: json.dumps({'version': version}).encode())
    def unexpected_send(*_):
        pytest.fail('An unsupported agent must not receive the check')
    monkeypatch.setattr(smon_agent, 'send_check_to_agent', unexpected_send)
    with pytest.raises(ValueError, match='Agent 1.20 or later'):
        smon_agent.send_http_checks(1, 'agent.example.test')


def test_unavailable_policy_support_does_not_block_default_checks(
    client, auth_headers, check_agent, monkeypatch
):
    sent = []
    monkeypatch.setattr(smon_agent, 'send_check_to_agent', lambda *args: sent.append(args[-1]))
    monkeypatch.setattr(smon_agent, 'send_get_request_to_agent', lambda *_: b'{"version":"2.0"}')
    for policy in ('default', 'require_https'):
        payload = _payload('http', check_agent.id, uuid.uuid4().hex)
        payload['ssl_policy'] = policy
        response = client.post('/api/v1.0/rmon/check/http', json=payload, headers=auth_headers(2, 1))
        assert response.status_code == 201
    sent.clear()
    monkeypatch.setattr(smon_agent, 'send_get_request_to_agent', lambda *_: b'{"version":"1.19"}')
    with pytest.raises(ValueError, match='Agent 1.20 or later'):
        smon_agent.send_http_checks(check_agent.id, check_agent.server_id.ip)
    assert len(sent) == 1
    assert sent[0]['fail_if_not_ssl'] is False
    assert sent[0]['fail_if_ssl'] is False
