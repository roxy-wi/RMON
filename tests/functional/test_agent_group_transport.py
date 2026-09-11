import configparser
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import uuid
from unittest.mock import Mock
from flask import g, render_template_string

import pytest
from peewee import SqliteDatabase
from playhouse.migrate import SqliteMigrator

from app.modules.common import agent_transport as transport
from app.modules.db import group as group_sql
from app.modules.db.db_model import Groups, Setting, Server, SmonAgent, InstallationTasks
from app.modules.roxywi.class_models import RmonAgent
from app.modules.service import installation
from app.modules.tools import smon_agent


@pytest.fixture
def owned_agent(tmp_path, monkeypatch):
    group = Groups.create(name=uuid.uuid4().hex, description='Transport test')
    group_sql.add_setting_for_new_group(group.group_id)
    server = Server.create(hostname='transport-test', ip=f'{uuid.uuid4().hex}.test', group_id=group.group_id)
    agent = SmonAgent.create(server_id=server, name='Transport test', uuid=str(uuid.uuid4()), description='')
    monkeypatch.setenv('RMON_AGENT_CERTIFICATES_DIR', str(tmp_path / 'certificates'))
    config = configparser.ConfigParser()
    config['agent_deployment'] = {'mtls_enabled': 'true', 'tls_ca_file': '/another-group/ca.crt'}
    monkeypatch.setattr(smon_agent, 'GetConfigVar', lambda: SimpleNamespace(config=config))
    get_setting = smon_agent.sql.get_setting
    receiver_settings = {'master_ip': 'receiver.test', 'master_port': '5100'}
    monkeypatch.setattr(smon_agent.sql, 'get_setting', lambda key, **kwargs:
                        receiver_settings[key] if key in receiver_settings else get_setting(key, **kwargs))
    yield agent
    InstallationTasks.delete().where(InstallationTasks.server_id == server).execute()
    SmonAgent.delete().where(SmonAgent.server_id == server).execute()
    server.delete_instance()
    group_sql.delete_group(group.group_id)


def set_value(agent, key, value):
    Setting.update(value=value).where((Setting.group_id == agent.server_id.group_id) & (Setting.param == key)).execute()


def test_new_groups_have_independent_settings(owned_agent):
    values = transport.group_settings(owned_agent.server_id.group_id)
    assert values == transport.DEFAULTS
    set_value(owned_agent, 'agent_result_transport', 'mtls')
    assert transport.group_settings(1)['agent_result_transport'] == 'http'


def test_explicit_group_mtls_paths_reach_role(owned_agent):
    group_id = owned_agent.server_id.group_id
    root = transport.certificate_root(group_id)
    root.mkdir(parents=True)
    for name, key in [('ca.crt', 'agent_tls_ca_file'), ('ca.key', 'agent_tls_ca_key_file')]:
        path = root / name
        path.write_text('test file; real PEM validation is done by the role')
        set_value(owned_agent, key, path.as_posix())
    inv, _ = smon_agent.generate_agent_inv('host.test', 'install', owned_agent.uuid,
                                          group_id=group_id, result_transport='mtls')
    settings = inv['server']['hosts']['host.test']
    assert settings['agent_transport'] == 'mtls'
    assert settings['agent_tls_ca_file'] == (root / 'ca.crt').as_posix()
    assert settings['agent_tls_ca_key_file'] == (root / 'ca.key').as_posix()
    assert settings['agent_certificate_directory'] == root.as_posix()
    assert settings['agent_verify_result_connection'] is True


@pytest.mark.parametrize('value', ['../other/ca.key', '/etc/passwd', '/var/lib/rmon/keys/agent-certificates/1/ca.key', '{{ secret }}', '/tmp/a\nkey'])
def test_certificate_paths_cannot_escape_the_group(owned_agent, value):
    with pytest.raises(ValueError):
        transport.validate_setting('agent_tls_ca_key_file', value, owned_agent.server_id.group_id)


def test_uuid_template_uses_persisted_agent_identity(owned_agent):
    group_id = owned_agent.server_id.group_id
    root = transport.certificate_root(group_id)
    path = root / '{uuid}' / 'client.pem'
    assert transport.certificate_path(path.as_posix(), group_id, owned_agent.uuid) == (
        root / owned_agent.uuid / 'client.pem').as_posix()
    with pytest.raises(ValueError, match='CA path'):
        transport.validate_setting('agent_tls_ca_file', path.as_posix(), group_id)


def test_missing_file_is_rejected_before_launch(owned_agent):
    group_id = owned_agent.server_id.group_id
    set_value(owned_agent, 'agent_tls_ca_file', (transport.certificate_root(group_id) / 'missing.pem').as_posix())
    with pytest.raises(ValueError, match='missing'):
        transport.inventory_settings(group_id, owned_agent.uuid, 'https')


def test_legacy_reconfigure_preserves_transport(owned_agent, monkeypatch):
    run = Mock(return_value=42)
    monkeypatch.setattr(smon_agent, 'run_ansible_thread', run)
    smon_agent.reconfigure_agent(owned_agent.id)
    host = run.call_args.args[0]['server']['hosts'][owned_agent.server_id.ip]
    assert 'agent_transport' not in host
    assert 'agent_tls_ca_file' not in host


def test_save_does_not_apply_and_success_records_selected_mode(owned_agent, monkeypatch):
    run = Mock(return_value=42)
    monkeypatch.setattr(smon_agent, 'run_ansible_thread', run)
    body = RmonAgent(name=owned_agent.name, server_id=owned_agent.server_id_id, result_transport='https')
    smon_agent.update_agent(owned_agent.id, body)
    run.assert_not_called()
    agent = SmonAgent.get_by_id(owned_agent.id)
    assert agent.result_transport == 'https' and transport.pending(agent)
    smon_agent.reconfigure_agent(agent.id)
    inv = run.call_args.args[0]
    transport.record_applied(inv)
    agent = SmonAgent.get_by_id(agent.id)
    assert agent.applied_result_transport == 'https' and agent.transport_checked_at is not None
    assert not transport.pending(agent)
    set_value(agent, 'agent_tls_ca_file', (transport.certificate_root(agent.server_id.group_id) / 'new-ca.pem').as_posix())
    assert transport.pending(agent)


def test_failed_task_does_not_claim_new_transport(owned_agent, monkeypatch):
    owned_agent.applied_result_transport = 'http'
    owned_agent.result_transport = 'https'
    owned_agent.save()
    task = InstallationTasks.create(service_name='Agent', server_id=owned_agent.server_id,
                                    user_id=1, group_id=owned_agent.server_id.group_id, action='reconfigure')
    inv, hosts = smon_agent.generate_agent_inv(owned_agent.server_id.ip, 'install', owned_agent.uuid,
        group_id=owned_agent.server_id.group_id, result_transport='https')
    monkeypatch.setattr(installation, 'run_ansible', Mock(return_value={'failures': {'host': 1}, 'dark': {}}))
    installation.run_installations(inv, hosts, 'rmon_agent', task.id)
    assert SmonAgent.get_by_id(owned_agent.id).applied_result_transport == 'http'
    assert InstallationTasks.get_by_id(task.id).status == 'failed'


def test_successful_task_records_the_verified_mode(owned_agent, monkeypatch):
    task = InstallationTasks.create(service_name='Agent', server_id=owned_agent.server_id,
                                    user_id=1, group_id=owned_agent.server_id.group_id, action='reconfigure')
    inv, hosts = smon_agent.generate_agent_inv(owned_agent.server_id.ip, 'install', owned_agent.uuid,
        group_id=owned_agent.server_id.group_id, result_transport='https')
    monkeypatch.setattr(installation, 'run_ansible', Mock(return_value={'failures': {}, 'dark': {}}))
    installation.run_installations(inv, hosts, 'rmon_agent', task.id)
    assert InstallationTasks.get_by_id(task.id).status == 'completed'
    agent = SmonAgent.get_by_id(owned_agent.id)
    assert agent.applied_result_transport == 'https'
    assert agent.transport_checked_at is not None


def test_agent_exists_before_background_installation(owned_agent, monkeypatch):
    owned_agent.delete_instance()
    set_value(owned_agent, 'agent_result_transport', 'https')
    monkeypatch.setattr(smon_agent, 'check_agent_limit', lambda: None)
    monkeypatch.setattr(smon_agent.roxywi_common, 'logger', Mock())
    def run(inv, *args):
        transport.record_applied(inv)
        return 42
    monkeypatch.setattr(smon_agent, 'run_ansible_thread', run)
    agent_id, task_id = smon_agent.add_agent(RmonAgent(name='New agent', server_id=owned_agent.server_id_id))
    agent = SmonAgent.get_by_id(agent_id)
    assert task_id == 42 and agent.result_transport == 'https'
    assert agent.applied_result_transport == 'https'


def test_group_settings_api_validates_paths(client, auth_headers, owned_agent):
    response = client.post('/api/v1.0/settings/agent', json={'param': 'agent_tls_ca_file', 'value': '/etc/passwd'}, headers=auth_headers(1, 1))
    assert response.status_code == 400
    assert transport.group_settings(1)['agent_tls_ca_file'] == ''


def test_settings_api_returns_only_requested_group_section(client, auth_headers, owned_agent):
    group_id = owned_agent.server_id.group_id
    set_value(owned_agent, 'agent_result_transport', 'mtls')
    response = client.get(f'/api/v1.0/settings/agent?group_id={group_id}', headers=auth_headers(1, 1))
    assert response.status_code == 200
    assert {row['param'] for row in response.json} == set(transport.DEFAULTS)
    assert all(int(row['group_id']) == group_id for row in response.json)
    assert next(row['value'] for row in response.json if row['param'] == 'agent_result_transport') == 'mtls'


def test_other_group_cannot_change_transport_settings(client, auth_headers, owned_agent):
    group_id = owned_agent.server_id.group_id
    response = client.post(f'/api/v1.0/settings/agent?group_id={group_id}',
                           json={'param': 'agent_result_transport', 'value': 'mtls'}, headers=auth_headers(2, 1))
    assert response.status_code == 404
    assert transport.group_settings(group_id)['agent_result_transport'] == 'http'


def test_transport_defaults_and_agent_status_api(client, auth_headers, owned_agent):
    response = client.get('/rmon/agent/transport-settings', headers=auth_headers(1, 1))
    assert response.status_code == 200 and response.json == {'result_transport': 'http'}
    response = client.get(f'/api/v1.0/rmon/agent/{owned_agent.id}', headers=auth_headers(1, 1))
    assert response.status_code == 200
    assert response.json['applied_result_transport'] is None
    assert 'uuid' not in response.json and 'transport_settings_hash' not in response.json


def test_migration_is_repeatable_and_preserves_legacy_agents(owned_agent, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'app/migrations/20260911000000_add_agent_result_transport.py'
    spec = importlib.util.spec_from_file_location('agent_transport_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db = SqliteDatabase(':memory:')
    db.execute_sql('CREATE TABLE smon_agents (id INTEGER PRIMARY KEY, uuid TEXT, port INTEGER)')
    db.execute_sql("INSERT INTO smon_agents VALUES (1, 'keep-uuid', 5101)")
    monkeypatch.setattr(module, 'connect', lambda get_migrator=False: SqliteMigrator(db) if get_migrator else db)
    module.upgrade()
    module.upgrade()
    row = db.execute_sql('SELECT uuid, port, result_transport, applied_result_transport FROM smon_agents').fetchone()
    assert row == ('keep-uuid', 5101, None, None)
    db.close()


@pytest.mark.parametrize('language', ['en', 'ru', 'fr', 'pt-br'])
def test_group_connection_controls_render(app, owned_agent, language):
    with app.test_request_context('/'):
        g.user_params = {'role': 2}
        markup = render_template_string(
            "{% import 'languages/' + language + '.html' as lang %}"
            "{% from 'include/input_macros.html' import input, checkbox %}"
            "{% include 'include/admin_settings.html' %}"
            "{% include 'include/agent_transport.html' %}",
            language=language,
            settings=Setting.select().where(Setting.group_id == owned_agent.server_id.group_id),
            agent_certificate_root=transport.certificate_root(owned_agent.server_id.group_id),
            timezones=['UTC'],
        )
        assert 'id="new-agent-result-transport"' in markup
        assert 'id="agent_tls_ca_file"' in markup
        assert 'HTTPS + mTLS' in markup
        assert 'Undefined' not in markup
