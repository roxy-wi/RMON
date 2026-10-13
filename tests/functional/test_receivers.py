import base64
import configparser
import concurrent.futures
import importlib.util
import json
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from flask import render_template_string

from app.modules.client_telemetry.models import ClientProject
from app.modules.client_telemetry.service import TelemetryError
from app.modules.db.db_model import Groups, InstallationTasks, Server, Setting, SmonAgent, conn
from app.modules.operations import queue
from app.modules.receivers import deployment, service
from app.modules.receivers.models import (AgentRouting, GroupReceiver, ReceiverEndpoint, ResultServer,
                                         ResultServerEndpoint, AppliedAgentReceiver, PendingAgentReceiver)
from app.modules.receivers.schemas import EndpointInput, RoutingInput, ServerInput, receiver_url
from app.modules.roxywi.class_models import RmonAgent
from app.modules.tools import smon_agent

pytestmark = pytest.mark.functional
API = '/api/v1.0/receivers'


@pytest.fixture
def setup(monkeypatch):
    group = Groups.create(name=uuid4().hex, description='Receivers test')
    hosts = [Server.create(hostname='result-' + str(i), ip=uuid4().hex + '.test', group_id=str(group.group_id)) for i in range(2)]
    config = configparser.ConfigParser(interpolation=None)
    config['pgsql'] = {'enable': '1', 'host': 'database', 'port': '5432', 'db': 'rmon',
                       'user': 'rmon', 'password': 'test-only-{{password}}'}
    monkeypatch.setattr(deployment, 'GetConfigVar', lambda: SimpleNamespace(config=config))
    monkeypatch.setenv('RMON_AGENT_CONTROL_URL', 'https://control.test')
    yield SimpleNamespace(group=group.group_id, hosts=hosts, config=config)
    for host in hosts:
        InstallationTasks.delete().where(InstallationTasks.server_id == host.server_id).execute()
    ResultServer.delete().where(ResultServer.host.in_(hosts)).execute()
    SmonAgent.delete().where(SmonAgent.server_id.in_(hosts)).execute()
    ClientProject.delete().where(ClientProject.group_id == group.group_id).execute()
    GroupReceiver.delete().where(GroupReceiver.group == group.group_id).execute()
    ReceiverEndpoint.delete().where(ReceiverEndpoint.group == group.group_id).execute()
    for host in hosts:
        host.delete_instance()
    group.delete_instance()


def address(setup, role='classic', **kwargs):
    data = dict(name='Shared LB', url='https://' + uuid4().hex + '.test', role=role, kind='lb', transport='https')
    data.update(kwargs)
    return service.save_endpoint(EndpointInput(**data), setup.group, admin=True)


def body(setup, endpoint, host=0, **kwargs):
    data = dict(name='Result server', host_id=setup.hosts[host].server_id,
                roles=[endpoint.role], endpoint_ids=[endpoint.id])
    data.update(kwargs)
    return ServerInput(**data)


@pytest.mark.parametrize('raw,expected', [('HTTPS://Example.COM:443/', 'https://example.com'),
    ('http://host.test:80', 'http://host.test'), ('https://[2001:db8::1]:5443/', 'https://[2001:db8::1]:5443')])
def test_canonical_addresses(raw, expected):
    assert receiver_url(raw) == expected


@pytest.mark.parametrize('raw', ['https://user:pass@host', 'https://host/path', 'https://host/?q=a',
    'https://host/#fragment', 'http://host:0', 'http://host:99999', 'https://host/\n', '{{url}}', 'file:///tmp'])
def test_invalid_addresses(raw):
    if raw.endswith('\n'):
        raw = 'https://ho\nst/'
    with pytest.raises(ValueError):
        receiver_url(raw)


def test_duplicate_endpoint_and_optimistic_lock(setup):
    endpoint = address(setup, url='https://METRICS.test:443/')
    with pytest.raises(TelemetryError) as error:
        address(setup, url='https://metrics.test')
    assert error.value.code == 'duplicate_receiver'
    data = EndpointInput(name='Updated', url=endpoint.url, role='classic', transport='https', kind='lb', revision=1)
    updated = service.save_endpoint(data, setup.group, endpoint_id=endpoint.id)
    assert updated.revision == 2
    with pytest.raises(TelemetryError) as error:
        service.save_endpoint(data, setup.group, endpoint_id=endpoint.id)
    assert error.value.code == 'revision_conflict'


def test_shared_address_has_one_row_for_multiple_servers(setup, monkeypatch):
    endpoint = address(setup)
    monkeypatch.setattr(deployment, 'enqueue', Mock(return_value=123))
    first, _ = deployment.configure(body(setup, endpoint), setup.group, 1)
    second, _ = deployment.configure(body(setup, endpoint, host=1), setup.group, 1)
    assert service.endpoint_json(endpoint)['server_ids'] == [first.id, second.id]
    assert ReceiverEndpoint.select().where(ReceiverEndpoint.group == setup.group).count() == 1
    service.save_defaults(setup.group, [endpoint.id])
    ResultServer.update(state='ready', applied_roles=['classic']).where(ResultServer.id == second.id).execute()
    deployment.ensure_detachable(first, [])
    ResultServerEndpoint.delete().where(ResultServerEndpoint.server == second).execute()
    with pytest.raises(TelemetryError) as error:
        deployment.action(first, 'stop', 1)
    assert error.value.code == 'server_in_use'


def test_queued_settings_are_encrypted_and_only_marked_applied_on_success(setup):
    endpoint = address(setup)
    server, task = deployment.configure(body(setup, endpoint), setup.group, 1)
    assert server.applied_revision == 0
    with pytest.raises(TelemetryError) as error:
        deployment.action(server, 'start', 1)
    assert error.value.code == 'operation_pending'
    claimed, owner = queue.claim()
    assert claimed == task
    payload = queue.load_payload(task, owner)
    values = payload['inventory']['server']['hosts'][setup.hosts[0].ip]
    config = base64.b64decode(values['result_server_config_b64']).decode()
    assert 'test-only-%7B%7Bpassword%7D%7D' in config and 'password' not in json.dumps(payload)
    assert payload['role'] == 'rmon_server'
    assert queue.finish(task, owner, on_success=lambda: deployment.record_applied(payload['inventory']))
    server = ResultServer.get_by_id(server.id)
    assert server.applied_revision == server.revision and server.applied_roles == ['classic']
    assert server.state == 'ready'


def test_failed_queue_rolls_back_server_and_nested_endpoint(setup, monkeypatch):
    monkeypatch.setattr(deployment, 'enqueue', Mock(side_effect=RuntimeError('queue unavailable')))
    new = EndpointInput(name='client', url='http://collector.test:5102', role='client')
    with pytest.raises(RuntimeError):
        deployment.configure(ServerInput(name='new', host_id=setup.hosts[0].server_id, roles=['client'], new_endpoints=[new]), setup.group, 1)
    assert not ResultServer.select().where(ResultServer.host == setup.hosts[0]).exists()
    assert not ReceiverEndpoint.select().where(ReceiverEndpoint.group == setup.group).exists()


def test_routing_defaults_explicit_and_applied_snapshot(setup):
    first, second = address(setup), address(setup)
    agent = SmonAgent.create(server_id=setup.hosts[0], uuid=str(uuid4()), name='Agent', description='')
    assert service.effective_routing(setup.group, service.routing_json(agent))['endpoints'] == []
    service.save_defaults(setup.group, [first.id])
    assert service.routing_pending(agent)
    selection = RoutingInput(endpoint_ids=[second.id, first.id], policy='failover')
    service.save_agent_routing(agent, selection)
    config = service.effective_routing(setup.group, service.routing_json(agent))
    assert config['endpoints'][0]['url'] == second.url and config['policy'] == 'failover'
    service.record_agent_applied({'server': {'hosts': {'test': {'action': 'install', 'agent_uuid': agent.uuid,
                              'agent_routing_hash': service.routing_hash(config)}}}})
    assert not service.routing_pending(agent)
    service.save_agent_routing(agent, RoutingInput())
    assert service.routing_pending(agent)
    with pytest.raises(TelemetryError):
        service.delete_endpoint(first)


def test_role_and_group_boundaries(setup):
    endpoint = address(setup)
    with pytest.raises(TelemetryError) as error:
        service.endpoint(endpoint.id, 1)
    assert error.value.status == 404
    ReceiverEndpoint.update(shared=True).where(ReceiverEndpoint.id == endpoint.id).execute()
    assert service.endpoint(endpoint.id, 1).id == endpoint.id
    with pytest.raises(TelemetryError):
        service.endpoint(endpoint.id, 1, owner=True)
    project = ClientProject.create(name='Project', group_id=setup.group, created_us=1)
    with pytest.raises(TelemetryError) as error:
        service.save_project_receiver(project, endpoint.id)
    assert error.value.code == 'receiver_role'
    client = address(setup, role='client')
    assert service.save_project_receiver(project, client.id)['ingest_url'] == client.url + '/api/v1/client/events'
    assert service.save_project_receiver(project, None)['ingest_url'] is None


def test_non_administrators_cannot_install(client, auth_headers, setup):
    for user in (2, 3):
        response = client.post(API + '/servers', json={'name': 'test', 'roles': ['classic'], 'host_id': setup.hosts[0].server_id}, headers=auth_headers(user, 1))
        assert response.status_code == 403


def test_configuration_does_not_expose_database_credentials(client, auth_headers, setup):
    response = client.get(API + '/configuration', headers=auth_headers(1, 1))
    assert response.status_code == 200, response.get_json()
    assert 'password' not in response.get_data(as_text=True)


@pytest.mark.parametrize('language', ['en', 'ru', 'fr', 'pt-br'])
def test_translations_are_exported(app, language):
    with app.test_request_context('/'):
        markup = render_template_string("{% import 'languages/' + language + '.html' as lang %}{{ lang.receivers|tojson }}", language=language)
    assert len(json.loads(markup)) >= 90


def test_sqlite_uses_existing_shared_file_in_separate_mount(setup):
    setup.config.remove_section('pgsql')
    endpoint = address(setup)
    server = ResultServer.create(host=setup.hosts[0], uuid=str(uuid4()), name='test', roles=['classic'])
    with pytest.raises(TelemetryError) as error:
        deployment.inventory(server, 'install')
    assert error.value.code == 'sqlite_path_required'
    server.sqlite_path = '/var/lib/rmon/rmon.db'
    inv, _ = deployment.inventory(server, 'install')
    values = inv['server']['hosts'][setup.hosts[0].ip]
    assert 'sqlite:////var/lib/rmon-shared/rmon.db' in base64.b64decode(values['result_server_config_b64']).decode()
    assert values['result_server_sqlite_path'] == '/var/lib/rmon/rmon.db'


def test_server_geoip_and_diagnostic_files_match_runtime_settings(setup):
    setup.config['server_deployment'] = {
        'client_geoip_database': '/opt/rmon/geoip/country.mmdb',
        'client_trusted_proxies': '172.18.0.0/16',
        'internal_api_token_file': '/etc/rmon/server-token',
    }
    server = ResultServer.create(host=setup.hosts[0], uuid=str(uuid4()), name='test', roles=['classic', 'client'])
    inv, _ = deployment.inventory(server, 'install')
    values = inv['server']['hosts'][setup.hosts[0].ip]
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(base64.b64decode(values['result_server_config_b64']).decode())
    assert config['rmon-server']['client_geoip_db'] == '/etc/rmon/managed/client_geoip_database'
    assert config['rmon-server']['client_trusted_proxies'] == '172.18.0.0/16'
    assert config['rmon-server']['internal_api_token_file'] == '/etc/rmon/managed/internal_api_token_file'
    assert values['result_server_files'] == [
        {'source': '/etc/rmon/server-token', 'name': 'internal_api_token_file'},
        {'source': '/opt/rmon/geoip/country.mmdb', 'name': 'client_geoip_database'},
    ]


def test_agent_save_and_queue_are_atomic(setup, monkeypatch):
    agent = SmonAgent.create(server_id=setup.hosts[0], uuid=str(uuid4()), name='old', description='')
    endpoint = address(setup, url='http://receiver.test:5100', transport='http')
    monkeypatch.setattr(smon_agent, 'run_ansible_thread', Mock(side_effect=RuntimeError('queue unavailable')))
    with pytest.raises(RuntimeError):
        smon_agent.update_agent(agent.id, RmonAgent(name='new', server_id=setup.hosts[0].server_id, reconfigure=True,
                                                  receivers=RoutingInput(endpoint_ids=[endpoint.id])))
    assert SmonAgent.get_by_id(agent.id).name == 'old'
    assert not AgentRouting.select().where(AgentRouting.agent == agent.id).exists()


def test_transport_pending_uses_selected_receivers_instead_of_legacy_mode(setup):
    from app.modules.common import agent_transport
    agent = SmonAgent.create(server_id=setup.hosts[0], uuid=str(uuid4()), name='Agent', description='', result_transport='http')
    endpoint = address(setup)
    service.save_agent_routing(agent, RoutingInput(endpoint_ids=[endpoint.id]))
    values = agent_transport.inventory_settings(setup.group, agent.uuid, 'https')
    values.update(action='install', agent_uuid=agent.uuid,
                  agent_routing_hash=service.routing_hash(service.effective_routing(setup.group, service.routing_json(agent))))
    agent_transport.record_applied({'server': {'hosts': {'test': values}}})
    assert not agent_transport.pending(SmonAgent.get_by_id(agent.id))


def test_concurrent_stops_cannot_remove_every_server(setup):
    endpoint = address(setup)
    servers = [ResultServer.create(host=host, uuid=str(uuid4()), name='server', roles=['classic'],
               state='ready', applied_roles=['classic']) for host in setup.hosts]
    for server in servers:
        ResultServerEndpoint.create(server=server, endpoint=endpoint)
    service.save_defaults(setup.group, [endpoint.id])
    def stop(server):
        try:
            deployment.action(server, 'stop', 1)
            return 'queued'
        except TelemetryError as error:
            return error.code
        finally:
            conn.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(stop, servers))
    assert sorted(outcomes) == ['queued', 'server_in_use']


def test_previous_receiver_is_retained_until_new_configuration_is_applied(setup):
    first, second = address(setup), address(setup)
    agent = SmonAgent.create(server_id=setup.hosts[0], uuid=str(uuid4()), name='Agent', description='')
    service.save_agent_routing(agent, RoutingInput(endpoint_ids=[first.id]))
    AppliedAgentReceiver.create(agent=agent, endpoint=first)
    service.save_agent_routing(agent, RoutingInput(endpoint_ids=[second.id]))
    with pytest.raises(TelemetryError) as error:
        service.delete_endpoint(first)
    assert error.value.code == 'receiver_in_use'
    config = service.effective_routing(setup.group, service.routing_json(agent))
    service.record_agent_applied({'server': {'hosts': {'test': {'action': 'install', 'agent_uuid': agent.uuid,
        'agent_receiver_ids': config['endpoint_ids'], 'agent_routing_hash': service.routing_hash(config)}}}})
    service.delete_endpoint(first)
    assert service.endpoint_json(second)['agent_count'] == 1


def test_queued_and_uncertain_receiver_survives_later_draft_changes(setup):
    endpoint = address(setup)
    agent = SmonAgent.create(server_id=setup.hosts[0], uuid=str(uuid4()), name='Agent', description='')
    config = service.effective_routing(setup.group, {'endpoint_ids': [endpoint.id], 'policy': 'balance'})
    host = {'action': 'install', 'agent_uuid': agent.uuid, 'agent_receiver_ids': config['endpoint_ids'],
            'agent_routing_hash': service.routing_hash(config)}
    task = queue.enqueue({'server': {'hosts': {setup.hosts[0].ip: host}}}, [setup.hosts[0].ip], 'rmon_agent', 'Agent', 'install', 1)
    service.save_agent_routing(agent, RoutingInput())
    with pytest.raises(TelemetryError):
        service.delete_endpoint(endpoint)
    claimed, owner = queue.claim()
    assert claimed == task and queue.finish(task, owner, error='SSH interrupted')
    assert service.routing_pending(agent)
    assert PendingAgentReceiver.select().where(PendingAgentReceiver.task == task).exists()
    # A later successful application of group defaults resolves the uncertainty.
    current = service.effective_routing(setup.group, service.routing_json(agent))
    service.record_agent_applied({'server': {'hosts': {'test': {'action': 'install', 'agent_uuid': agent.uuid,
        'agent_receiver_ids': [], 'agent_routing_hash': service.routing_hash(current)}}}})
    assert not service.routing_pending(agent)
    service.delete_endpoint(endpoint)


def test_migration_imports_legacy_addresses_once_without_switching_agents():
    path = Path(__file__).parents[2] / 'app/migrations/20260930000000_add_result_servers.py'
    spec = importlib.util.spec_from_file_location('receiver_migration', path)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    setting = Setting.get((Setting.param == 'master_ip') & (Setting.group_id == 1))
    previous = setting.value
    known_ids = [e.id for e in ReceiverEndpoint.select()]
    defaults = service.defaults(1)
    try:
        Setting.update(value='old-receiver.test,old-receiver.test').where((Setting.param == 'master_ip') & (Setting.group_id == 1)).execute()
        migration.upgrade(); migration.upgrade()
        imported = list(ReceiverEndpoint.select().where(ReceiverEndpoint.id.not_in(known_ids)))
        assert len(imported) == 1 and imported[0].kind == 'external'
        assert not imported[0].shared and service.defaults(1) == defaults
    finally:
        Setting.update(value=previous).where((Setting.param == 'master_ip') & (Setting.group_id == 1)).execute()
        ReceiverEndpoint.delete().where(ReceiverEndpoint.id.not_in(known_ids)).execute()
