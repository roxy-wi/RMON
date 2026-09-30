"""Render actual chart variants with Helm and validate their Kubernetes contracts."""
import os
from pathlib import Path
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
HELM = os.getenv('RMON_TEST_HELM_BINARY', 'helm')
BASE = {'publicURL': 'https://rmon.example.test', 'existingConfigSecret': 'settings',
        'server': {'existingTokenSecret': 'receiver'}}


def render(values, *, valid=True):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'values.yaml'
        path.write_text(yaml.safe_dump(values), encoding='utf-8')
        result = subprocess.run([HELM, 'template', 'test', str(ROOT / 'helm/rmon'), '-f', str(path)],
                                text=True, capture_output=True, check=False)
    if not valid:
        assert result.returncode != 0, values
        return
    assert result.returncode == 0, result.stderr
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def deployments(docs):
    return {d['metadata']['labels']['app.kubernetes.io/component']: d for d in docs if d['kind'] == 'Deployment'}


def validate_server_roles():
    for roles in (['classic'], ['client'], ['classic', 'client']):
        values = {**BASE, 'server': {**BASE['server'], 'roles': roles,
                  'externalURL': 'https://classic.example.test:5100',
                  'client': {'workers': 3, 'threads': 5, 'geoipDatabase': '/etc/geo/country.mmdb',
                             'trustedProxies': '192.0.2.1/32'}},
                  'ingress': {'enabled': True, 'host': 'rmon.example.test'}}
        docs = render(values)
        apps = deployments(docs)
        container = apps['server']['spec']['template']['spec']['containers'][0]
        env = {v['name']: v.get('value') for v in container['env']}
        assert env['RMON_SERVER_ROLES'] == ','.join(roles)
        assert container['command'] == ['python', '-m', 'modules.common.runtime']
        for name, kind in [('startupProbe', 'ready'), ('readinessProbe', 'ready'), ('livenessProbe', 'live')]:
            assert container[name]['exec']['command'] == ['python', '-m', 'modules.common.runtime', 'health', kind]
        services = {d['metadata']['name']: d for d in docs if d['kind'] == 'Service'}
        assert ('test-rmon-chart-server' in services) == ('classic' in roles)
        assert ('test-rmon-chart-client' in services) == ('client' in roles)
        ports = {p['containerPort'] for p in container['ports']}
        assert (5100 in ports) == ('classic' in roles)
        assert (5102 in ports) == ('client' in roles)
        ingress = next(d for d in docs if d['kind'] == 'Ingress')
        paths = ingress['spec']['rules'][0]['http']['paths']
        events = [p for p in paths if p['path'] == '/api/v1/client/events']
        assert bool(events) == ('client' in roles)
        if events:
            assert events[0]['pathType'] == 'Exact'
            assert events[0]['backend']['service'] == {'name': 'test-rmon-chart-client', 'port': {'number': 5102}}
            assert services['test-rmon-chart-client']['spec']['type'] == 'ClusterIP'
            assert env['RMON_CLIENT_WORKERS'] == '3' and env['RMON_CLIENT_THREADS'] == '5'
            assert env['RMON_CLIENT_BIND'] == '0.0.0.0:5102'
            assert env['RMON_CLIENT_GEOIP_DB'] == '/etc/geo/country.mmdb'
            assert env['RMON_CLIENT_TRUSTED_PROXIES'] == '192.0.2.1/32'
        web = apps['web']['spec']['template']['spec']['containers'][0]
        web_env = {v['name']: v.get('value') for v in web['env']}
        assert web_env['RMON_SERVER_INTERNAL_URL'] == ('http://test-rmon-chart-server:5100' if 'classic' in roles else 'https://classic.example.test:5100')

    # A client-only server does not need classic TLS identities or diagnostics.
    docs = render({**BASE, 'server': {**BASE['server'], 'roles': ['client'], 'transport': 'mtls'}})
    for app in deployments(docs).values():
        pod = app['spec']['template']['spec']
        assert not any(v['name'] in ('client-tls', 'server-tls') for v in pod['volumes'])
        env = {v['name']: v.get('value') for v in pod['containers'][0]['env']}
        assert 'RMON_SERVER_INTERNAL_URL' not in env
        assert 'RMON_SERVER_TRANSPORT' not in env
    # With both roles, agent mTLS and the public HTTP collector stay separate.
    docs = render({**BASE, 'server': {**BASE['server'], 'roles': ['classic', 'client'], 'transport': 'mtls',
                   'tls': {'existingServerSecret': 'identity', 'existingClientSecret': 'client'}}})
    container = deployments(docs)['server']['spec']['template']['spec']['containers'][0]
    env = {v['name']: v.get('value') for v in container['env']}
    assert env['RMON_SERVER_TRANSPORT'] == 'mtls' and env['RMON_CLIENT_BIND'] == '0.0.0.0:5102'
    docs = render({**BASE, 'server': {**BASE['server'], 'enabled': False, 'roles': ['classic', 'client']},
                   'ingress': {'enabled': True, 'host': 'rmon.example.test'}})
    assert not any(d['metadata']['name'].endswith('-client') for d in docs)
    for roles in ([], ['unknown'], ['classic', 'classic'], ['client', 'client'], 'client'):
        render({**BASE, 'server': {**BASE['server'], 'roles': roles}}, valid=False)
    render({**BASE, 'server': {**BASE['server'], 'client': {'workers': 0}}}, valid=False)


def main():
    validate_server_roles()
    docs = render(BASE)
    apps = deployments(docs)
    assert set(apps) == {'web', 'scheduler', 'operations', 'server'}
    assert not any(d['kind'] == 'Secret' for d in docs)
    for role, app in apps.items():
        assert app['metadata']['name'] == 'test-rmon-chart-' + role
        assert app['spec']['selector']['matchLabels'] == {
            'app.kubernetes.io/name': 'rmon-chart',
            'app.kubernetes.io/instance': 'test',
            'app.kubernetes.io/component': role,
        }
        assert app['spec']['replicas'] == 1
        assert app['spec']['strategy']['type'] == 'Recreate'
        pod = app['spec']['template']['spec']
        assert not pod['automountServiceAccountToken']
        assert pod['securityContext']['fsGroup'] == 33
        assert 'affinity' in pod
        container = pod['containers'][0]
        expected_image = ('ghcr.io/roxy-wi/rmon/rmon-server:7.0' if role == 'server'
                          else 'ghcr.io/roxy-wi/rmon/rmon-web:1.4.0')
        assert container['image'] == expected_image
        if role != 'server':
            env = {v['name']: v.get('value') for v in container['env']}
            assert env['RMON_AGENT_IMAGE'] == 'ghcr.io/roxy-wi/rmon/rmon-agent:2.0'
        assert all(p in container for p in ('livenessProbe', 'readinessProbe', 'startupProbe'))
        volumes = {v['name'] for v in pod['volumes']}
        assert all(m['name'] in volumes for m in container['volumeMounts'])
    claim = next(d for d in docs if d['kind'] == 'PersistentVolumeClaim')
    assert claim['metadata']['name'] == 'test-rmon-chart-data'
    assert apps['operations']['spec']['template']['spec']['terminationGracePeriodSeconds'] == 1800
    maintenance = deployments(render({**BASE, 'maintenance': True}))
    assert all(a['spec']['replicas'] == 0 for a in maintenance.values())
    migration = render({**BASE, 'maintenance': True, 'migration': {'enabled': True}})
    job = next(d for d in migration if d['kind'] == 'Job')
    assert job['spec']['template']['spec']['containers'][0]['args'] == ['/var/www/rmon/app/migrate.py', 'migrate']
    assert 'affinity' not in job['spec']['template']['spec']
    config = {'main': {'secret_phrase': 'A' * 43 + '='}, 'pgsql': {'enable': 1, 'host': 'db.example'}}
    docs = render({**BASE, 'existingConfigSecret': '', 'config': config,
                   'persistence': {'accessModes': ['ReadWriteMany']},
                   'bootstrap': {'enabled': True, 'existingSecret': 'initial-password'},
                   'ingress': {'enabled': True, 'host': 'rmon.example.test', 'tls': [{'secretName': 'web-tls', 'hosts': ['rmon.example.test']}]}})
    secret = next(d for d in docs if d['kind'] == 'Secret')
    assert 'port = 5432' in secret['stringData']['rmon.cfg']
    assert all('affinity' not in d['spec']['template']['spec'] for d in deployments(docs).values())
    assert deployments(docs)['web']['spec']['template']['spec']['initContainers'][0]['args'] == ['bootstrap']
    assert any(d['kind'] == 'Ingress' for d in docs)
    for mode in ('https', 'mtls'):
        docs = render({**BASE, 'server': {**BASE['server'], 'transport': mode,
                       'tls': {'existingServerSecret': 'identity', 'existingClientSecret': 'client'}}})
        for role, app in deployments(docs).items():
            volumes = app['spec']['template']['spec']['volumes']
            assert any(v['name'] == 'server-tls' for v in volumes) == (role == 'server')
            assert any(v['name'] == 'client-tls' for v in volumes)
    docs = render({**BASE, 'server': {'enabled': False, 'externalURL': 'https://receiver.test', 'existingTokenSecret': 'token'},
                   'persistence': {'existingClaim': 'restored-data'},
                   'image': {'digest': 'sha256:' + 'a' * 64}})
    assert 'server' not in deployments(docs)
    assert not any(d['kind'] == 'PersistentVolumeClaim' for d in docs)
    assert '@sha256:' in deployments(docs)['web']['spec']['template']['spec']['containers'][0]['image']
    for invalid in (
        {}, {**BASE, 'publicURL': ''}, {**BASE, 'web': {'replicaCount': 2}},
        {**BASE, 'migration': {'enabled': True}},
        {**BASE, 'bootstrap': {'enabled': True}}, {**BASE, 'server': {'transport': 'mtls'}},
        {**BASE, 'persistence': {'accessModes': ['ReadWriteOncePod']}},
        {**BASE, 'existingConfigSecret': '', 'config': {'main': {'secret_phrase': 'short'}}},
        {**BASE, 'existingConfigSecret': '', 'config': {'main': {'secret_phrase': 'A' * 43 + '='}}, 'persistence': {'accessModes': ['ReadWriteMany']}},
    ):
        render(invalid, valid=False)
    print('Helm rendering: classic/client roles, combined roles, probes, ingress, bootstrap, maintenance, PostgreSQL/RWX, HTTPS/mTLS, external server, restored PVC, digest and invalid settings passed')


if __name__ == '__main__':
    main()
