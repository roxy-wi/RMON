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


def main():
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
    print('Helm rendering: default, bootstrap, maintenance, PostgreSQL/RWX, ingress, HTTPS/mTLS, external server, restored PVC, digest and invalid settings passed')


if __name__ == '__main__':
    main()
