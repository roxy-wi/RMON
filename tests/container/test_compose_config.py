"""Validate resolved deployment contracts with Compose, without a Docker daemon."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def compose_config(tmp_path):
    executable = os.getenv('RMON_TEST_COMPOSE_BINARY')
    command = [executable] if executable else ['docker', 'compose']
    if not executable and not shutil.which('docker'):
        pytest.skip('Compose CLI is required; no Docker daemon is used')
    # Never resolve a developer's real deployment settings or secrets in a test.
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('RMON_', 'COMPOSE_', 'DOCKER_'))}
    environment['COMPOSE_DISABLE_ENV_FILE'] = 'true'
    env_file = tmp_path / 'test.env'

    def resolve(values=None, server=False):
        env_file.write_text('\n'.join(f"{key}='{value}'" for key, value in (values or {}).items()), encoding='utf-8')
        args = [*command, '--project-name', 'rmon-compose-test', '--project-directory', str(tmp_path),
                '--env-file', str(env_file), '-f', str(ROOT / 'compose.yaml')]
        if server:
            args += ['-f', str(ROOT / 'compose.server.yaml')]
        result = subprocess.run([*args, 'config', '--format', 'json'], env=environment,
                                cwd=tmp_path, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        config = json.loads(result.stdout)
        # Compose versions serialize the list form as either a list or a map.
        for service in config['services'].values():
            settings = service.get('environment') or {}
            if isinstance(settings, list):
                settings = dict(entry.split('=', 1) for entry in settings if '=' in entry)
            service['environment'] = settings
        return config

    return resolve


def mounts(service):
    return {mount['target']: mount for mount in service['volumes']}


def test_default_deployment_keeps_local_images_and_separates_tls(compose_config):
    config = compose_config()
    assert set(config['services']) == {'web', 'proxy', 'scheduler', 'operations'}
    web, proxy = config['services']['web'], config['services']['proxy']
    assert web['image'] == 'rmon-web:local'
    assert proxy['image'] == 'rmon-proxy:local'
    assert not web.get('ports')
    assert '/etc/ssl/certs/rmon' not in mounts(web)
    assert proxy['environment']['RMON_SELF_SIGNED'] == '1'
    assert not web['environment'].get('RMON_SECRET_PHRASE')
    assert any('host.docker.internal' in host for host in web['extra_hosts'])
    for role in ('scheduler', 'operations'):
        service = config['services'][role]
        assert service['command'] == [role]
        assert service['image'] == web['image']
        assert not service.get('ports')
        assert mounts(service) == mounts(web)
        assert service['healthcheck']['test'][-2:] == ['--role', role]


def test_dotenv_preserves_literal_secrets_and_external_server_settings(compose_config):
    values = {
        'RMON_WEB_IMAGE': 'example.invalid/rmon:web-test',
        'RMON_PROXY_IMAGE': 'example.invalid/rmon:proxy-test',
        'RMON_PUBLIC_URL': 'https://rmon.example.net',
        'RMON_SECRET_KEY': 'test-only-literal-$value#with-special-characters',
        'RMON_SECRET_PHRASE': 'test-only-credential-key',
        'RMON_JWT_ALGORITHM': 'HS256',
        'RMON_JWT_SECRET_KEY': 'test-only-jwt-key',
        'RMON_CONFIG_FILE': '/etc/rmon/custom.cfg',
        'RMON_DB_PATH': '/var/lib/rmon/custom.db',
        'RMON_SERVER_INTERNAL_URL': 'https://receiver.example.net:5100',
        'RMON_SERVER_INTERNAL_TOKEN_FILE': '/etc/rmon/secrets/token',
        'RMON_SERVER_CA_FILE': '/etc/rmon/tls/ca.crt',
        'RMON_SERVER_CLIENT_CERT_FILE': '/etc/rmon/tls/web.crt',
        'RMON_SERVER_CLIENT_KEY_FILE': '/etc/rmon/tls/web.key',
    }
    services = compose_config(values)['services']
    assert services['web']['image'] == values['RMON_WEB_IMAGE']
    assert services['proxy']['image'] == values['RMON_PROXY_IMAGE']
    for key, value in values.items():
        if key not in ('RMON_WEB_IMAGE', 'RMON_PROXY_IMAGE'):
            # The canonical config escapes literal dollars for safe reloading.
            assert services['web']['environment'][key] == value.replace('$', '$$')
    assert 'RMON_SECRET_KEY' not in services['proxy']['environment']
    assert 'RMON_JWT_SECRET_KEY' not in services['proxy']['environment']


def test_same_host_server_shares_config_database_and_token(compose_config):
    config = compose_config(server=True)
    web, server = (config['services'][name] for name in ('web', 'server'))
    assert server['image'] == 'ghcr.io/roxy-wi/rmon-server:7.0'
    assert server['user'] == '33:33'
    for target in ('/etc/rmon', '/var/lib/rmon'):
        assert mounts(web)[target]['source'] == mounts(server)[target]['source']
    assert mounts(server)['/etc/rmon']['read_only'] is True
    assert not mounts(server)['/var/lib/rmon'].get('read_only', False)
    assert server['read_only'] is True and server['cap_drop'] == ['ALL']
    assert not server.get('privileged')
    assert server['ports'][0]['host_ip'] == '127.0.0.1'
    assert server['depends_on']['web']['condition'] == 'service_healthy'
    assert web['secrets'][0]['source'] == server['secrets'][0]['source'] == 'rmon_server_token'
    assert web['environment']['RMON_SERVER_INTERNAL_TOKEN_FILE'] == server['environment']['RMON_INTERNAL_API_TOKEN_FILE']
    assert web['environment']['RMON_SERVER_INTERNAL_URL'] == 'http://server:5100'
    # Unset environment overrides must leave existing server TLS settings usable.
    assert not server['environment'].get('RMON_SERVER_TRANSPORT')


def test_existing_directories_are_shared_in_both_services(compose_config, tmp_path):
    values = {}
    for kind in ('CONFIG', 'DATA', 'LOG', 'TLS'):
        directory = tmp_path / kind.lower()
        directory.mkdir()
        values[f'RMON_{kind}_SOURCE'] = directory.as_posix()
    values.update({'RMON_CONFIG_FILE': '/etc/rmon/custom.cfg', 'RMON_DB_PATH': '/var/lib/rmon/custom.db',
                   'RMON_SELF_SIGNED': '0', 'RMON_SERVER_BIND_IP': '192.0.2.10', 'RMON_SERVER_PORT': '5510',
                   'RMON_SERVER_IMAGE': 'example.invalid/rmon-server:pinned'})
    services = compose_config(values, server=True)['services']
    assert services['server']['image'] == values['RMON_SERVER_IMAGE']
    for target in ('/etc/rmon', '/var/lib/rmon'):
        web_mount = mounts(services['web'])[target]
        server_mount = mounts(services['server'])[target]
        assert web_mount['type'] == server_mount['type'] == 'bind'
        assert web_mount['source'] == server_mount['source']
    for key in ('RMON_CONFIG_FILE', 'RMON_DB_PATH'):
        assert services['web']['environment'][key] == services['server']['environment'][key] == values[key]
    assert mounts(services['proxy'])['/etc/ssl/certs/rmon']['type'] == 'bind'
    assert services['proxy']['environment']['RMON_SELF_SIGNED'] == '0'
    assert services['server']['ports'][0]['host_ip'] == '192.0.2.10'
    assert services['server']['ports'][0]['published'] == '5510'


def test_server_tls_and_probe_settings_survive_compose(compose_config):
    server_values = {
        'RMON_SERVER_TRANSPORT': 'mtls',
        'RMON_TLS_CERT_FILE': '/etc/rmon/tls/server.crt',
        'RMON_TLS_KEY_FILE': '/etc/rmon/tls/server.key',
        'RMON_TLS_CA_FILE': '/etc/rmon/tls/ca.crt',
        'RMON_PROBE_SCHEME': 'https',
        'RMON_PROBE_CA_FILE': '/etc/rmon/tls/ca.crt',
        'RMON_PROBE_CLIENT_CERT_FILE': '/etc/rmon/tls/probe.crt',
        'RMON_PROBE_CLIENT_KEY_FILE': '/etc/rmon/tls/probe.key',
    }
    services = compose_config({**server_values, 'RMON_SERVER_INTERNAL_URL': 'https://server:5100'}, server=True)['services']
    for key, value in server_values.items():
        assert services['server']['environment'][key] == value
    assert services['web']['environment']['RMON_SERVER_INTERNAL_URL'] == 'https://server:5100'
    assert 'RMON_TLS_KEY_FILE' not in services['web']['environment']
