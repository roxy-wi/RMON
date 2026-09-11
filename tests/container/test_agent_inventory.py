import configparser
from types import SimpleNamespace
import uuid

import pytest

from app.modules.tools import smon_agent


@pytest.fixture
def config(monkeypatch):
    cfg = configparser.ConfigParser()
    monkeypatch.setattr(smon_agent, 'GetConfigVar', lambda: SimpleNamespace(config=cfg))
    monkeypatch.setattr(smon_agent.sql, 'get_setting', lambda key: {'master_ip': 'receiver.test', 'master_port': '5100'}[key])
    monkeypatch.delenv('RMON_AGENT_CONTROL_URL', raising=False)
    monkeypatch.delenv('RMON_AGENT_IMAGE', raising=False)
    return cfg


def test_existing_installation_does_not_implicitly_change_transport(config):
    inventory, hosts = smon_agent.generate_agent_inv('host.test', 'install', str(uuid.uuid4()))
    settings = inventory['server']['hosts']['host.test']
    assert hosts == ['host.test']
    assert 'agent_transport' not in settings and 'agent_mtls_enabled' not in settings
    assert settings['master_ip'] == 'receiver.test'


@pytest.mark.parametrize('configured,environment,expected', [
    (None, None, 'ghcr.io/roxy-wi/rmon-agent:2.0'),
    ('example.invalid/rmon-agent:pinned', None, 'example.invalid/rmon-agent:pinned'),
    ('example.invalid/rmon-agent:pinned', 'example.invalid/rmon-agent:custom',
     'example.invalid/rmon-agent:custom'),
])
def test_agent_image_default_and_explicit_overrides(config, monkeypatch, configured, environment, expected):
    if configured:
        config['agent_deployment'] = {'image': configured}
    if environment:
        monkeypatch.setenv('RMON_AGENT_IMAGE', environment)
    inventory, _ = smon_agent.generate_agent_inv('host.test', 'install', str(uuid.uuid4()))
    assert inventory['server']['hosts']['host.test']['agent_image'] == expected


def test_global_tls_settings_cannot_override_group_or_existing_agents(config):
    config['agent_deployment'] = {
        'transport': 'https', 'mtls_enabled': 'true', 'tls_generate': 'true',
        'tls_ca_file': '/run/issuer/ca.crt', 'tls_ca_key_file': '/run/issuer/ca.key',
        'bind_ip': '172.17.0.1', 'pull': 'never',
    }
    inventory, _ = smon_agent.generate_agent_inv('host.test', 'install', str(uuid.uuid4()))
    settings = inventory['server']['hosts']['host.test']
    assert 'agent_mtls_enabled' not in settings
    assert 'agent_tls_ca_key_file' not in settings
    assert 'agent_tls_ca_file' not in settings
    assert settings['agent_bind_ip'] == '172.17.0.1'
    assert settings['agent_pull'] == 'never'


def test_explicit_transport_requires_owner_group(config):
    with pytest.raises(ValueError, match='owner group'):
        smon_agent.generate_agent_inv('host.test', 'install', str(uuid.uuid4()), result_transport='mtls')
