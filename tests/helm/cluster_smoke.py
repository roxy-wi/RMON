"""Opt-in end-to-end test in a disposable Kind cluster owned by CI."""
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
NS = 'rmon-helm-test'
SELECTOR = 'app.kubernetes.io/instance=smoke'


def run(*args, input=None, timeout=900):
    result = subprocess.run(args, input=input, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{args[0:3]} failed:\n{result.stdout[-3000:]}\n{result.stderr[-3000:]}')
    return result.stdout


def kube(*args, **kwargs):
    return run('kubectl', '-n', NS, *args, **kwargs)


def secret(name, data):
    kube('apply', '-f', '-', input=json.dumps({'apiVersion': 'v1', 'kind': 'Secret',
         'metadata': {'name': name}, 'stringData': data}))


def execute(role, code):
    interpreter = 'python' if role == 'server' else '/opt/rmon-venv/bin/python'
    return kube('exec', '-i', 'deployment/smoke-rmon-' + role, '-c', role, '--', interpreter, '-', input=code)


def verify(password, expected=None):
    result = execute('web', f'''
import hashlib, json, os, sqlite3, urllib.request
from pathlib import Path
opener = urllib.request.build_opener(urllib.request.ProxyHandler({{}}))
base = 'http://smoke-rmon-web:8080'
assert opener.open(base + '/login', timeout=15).status == 200
request = urllib.request.Request(base + '/login', data=json.dumps({{'login': 'admin', 'pass': {password!r}}}).encode(), headers={{'Content-Type': 'application/json'}})
with opener.open(request, timeout=45) as response:
    assert json.load(response)['status'] == 'done'
os.environ['RMON_SCHEDULER_ENABLED'] = '0'
from app.modules.tools.common import _server_runtime_version
assert _server_runtime_version() == '7.0'
db = sqlite3.connect('/var/lib/rmon/rmon.db')
db.execute('CREATE TABLE IF NOT EXISTS helm_persistence_test (id INTEGER PRIMARY KEY, value TEXT)')
db.execute("INSERT OR IGNORE INTO helm_persistence_test VALUES (1, 'preserved')")
db.commit()
assert db.execute('SELECT value FROM helm_persistence_test').fetchone() == ('preserved',)
keys = {{p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/var/lib/rmon/keys').iterdir() if p.is_file()}}
assert 'rmon-key' in keys and 'rmon-key.pub' in keys
print(json.dumps(keys, sort_keys=True))
''')
    fingerprint = json.loads(result.strip().splitlines()[-1])
    if expected is not None:
        assert fingerprint == expected, 'Application keys changed after pod replacement'
    pods = json.loads(kube('get', 'pods', '-l', SELECTOR, '-o', 'json'))['items']
    running = [p for p in pods if p['metadata']['labels']['app.kubernetes.io/component'] != 'migration']
    assert len(running) == 4
    assert len({p['spec']['nodeName'] for p in running}) == 1, 'RWO pods must share a node'
    for role in ('scheduler', 'operations'):
        kube('exec', 'deployment/smoke-rmon-' + role, '--', '/opt/rmon-venv/bin/python', '-m',
             'container.runtime', 'healthcheck', '--role', role)
    kube('exec', 'deployment/smoke-rmon-server', '--', 'python', '-m', 'modules.common.probe', 'ready')
    return fingerprint


def main():
    # Refuse arbitrary clusters, including a developer's current production context.
    assert run('kubectl', 'config', 'current-context').strip() == 'kind-rmon-chart-test'
    run('kubectl', 'create', 'namespace', NS)
    password = secrets.token_urlsafe(24)
    secret('initial-password', {'admin-password': password})
    secret('receiver-token', {'token': secrets.token_urlsafe(32)})
    values = {'publicURL': 'http://smoke-rmon-web:8080', 'cookieSecure': False,
              'config': {'main': {'secret_phrase': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}},
              'image': {'repository': 'rmon-web-test', 'tag': 'ci', 'pullPolicy': 'Never'},
              'bootstrap': {'enabled': True, 'existingSecret': 'initial-password'},
              'server': {'existingTokenSecret': 'receiver-token', 'image': {'pullPolicy': 'Never'}},
              'persistence': {'size': '1Gi'}}
    with tempfile.TemporaryDirectory(prefix='rmon-chart-') as directory:
        directory = Path(directory)
        settings = directory / 'values.yaml'
        settings.write_text(yaml.safe_dump(values), encoding='utf-8')
        settings.chmod(0o600)

        def upgrade(*options):
            return run('helm', 'upgrade', '--install', 'smoke', str(ROOT / 'helm/rmon'), '-n', NS,
                       '-f', str(settings), '--wait', '--wait-for-jobs', '--timeout', '10m', *options)

        upgrade()
        before = verify(password)
        print('Fresh installation: login, all services, receiver API and RWO placement passed', flush=True)
        # A new initialization password must not reset an existing administrator.
        secret('initial-password', {'admin-password': secrets.token_urlsafe(24)})
        kube('delete', 'pods', '-l', SELECTOR, '--wait=true')
        kube('wait', 'deployment', '-l', SELECTOR, '--for=condition=Available', '--timeout=600s')
        # rollout status also observes the new deployment generation/readiness.
        for role in ('web', 'scheduler', 'operations', 'server'):
            kube('rollout', 'status', 'deployment/smoke-rmon-' + role, '--timeout=600s')
        verify(password, before)
        print('Pod replacement: original login, database marker and application keys preserved', flush=True)
        upgrade('--set', 'maintenance=true', '--set', 'bootstrap.enabled=false')
        kube('wait', 'pod', '-l', SELECTOR, '--for=delete', '--timeout=180s')
        upgrade('--set', 'maintenance=true', '--set', 'bootstrap.enabled=false', '--set', 'migration.enabled=true')
        jobs = json.loads(kube('get', 'jobs', '-l', SELECTOR, '-o', 'json'))['items']
        assert len(jobs) == 1 and jobs[0]['status'].get('succeeded') == 1
        upgrade('--set', 'bootstrap.enabled=false')
        verify(password, before)
        print('Explicit maintenance and app/migrate.py job passed', flush=True)
        # Exercise actual certificate mounts and authenticated probes, not only rendering.
        run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(directory / 'ca.key'),
            '-out', str(directory / 'ca.crt'), '-subj', '/CN=RMON CI CA', '-days', '1')
        for name, usage in [('server', 'serverAuth'), ('client', 'clientAuth')]:
            run('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(directory / f'{name}.key'),
                '-out', str(directory / f'{name}.csr'), '-subj', f'/CN={name}')
            extension = directory / f'{name}.ext'
            extension.write_text(f'extendedKeyUsage={usage}\nsubjectAltName=DNS:smoke-rmon-server,IP:127.0.0.1\n')
            run('openssl', 'x509', '-req', '-in', str(directory / f'{name}.csr'), '-CA', str(directory / 'ca.crt'),
                '-CAkey', str(directory / 'ca.key'), '-CAcreateserial', '-out', str(directory / f'{name}.crt'),
                '-days', '1', '-extfile', str(extension))
            secret('tls-' + name, {'tls.crt': (directory / f'{name}.crt').read_text(),
                                  'tls.key': (directory / f'{name}.key').read_text(),
                                  'ca.crt': (directory / 'ca.crt').read_text()})
        for mode in ('https', 'mtls'):
            upgrade('--set', 'bootstrap.enabled=false', '--set', 'server.transport=' + mode,
                    '--set', 'server.tls.existingServerSecret=tls-server',
                    '--set', 'server.tls.existingClientSecret=tls-client')
            verify(password, before)
            if mode == 'mtls':
                execute('web', '''
import ssl, urllib.request, urllib.error
context = ssl.create_default_context(cafile='/run/rmon-client-tls/ca.crt')
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context))
try:
    opener.open('https://smoke-rmon-server:5100/internal/health/live', timeout=5)
except urllib.error.HTTPError:
    raise AssertionError('mTLS accepted a connection without a client certificate')
except (urllib.error.URLError, ssl.SSLError, ConnectionError):
    pass
else:
    raise AssertionError('mTLS did not require a client certificate')
''')
            print(mode.upper() + ': receiver API and authenticated probes passed', flush=True)
        run('helm', 'uninstall', 'smoke', '-n', NS, '--wait')
        assert kube('get', 'pvc', 'smoke-rmon-data', '-o', 'name').strip()
        print('Uninstall preserved the data volume', flush=True)


if __name__ == '__main__':
    main()
