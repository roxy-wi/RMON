"""Opt-in Linux integration check using an existing, authorized SSH host.

Owns a separate Compose project, database and agent directory. SSH credentials
stay on the host and are re-encrypted into the temporary database, never logged.
"""
import argparse
import configparser
from contextlib import closing
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler, HTTPCookieProcessor, Request
from uuid import uuid4


def run(*args, check=True, timeout=180, **kwargs):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)
    if check and result.returncode:
        raise RuntimeError(f'{args[0]} failed: {result.stderr[-3000:]}')
    return result


def free_port(address):
    with socket.socket() as listener:
        listener.bind((address, 0))
        return listener.getsockname()[1]


def exercise(args):
    if os.geteuid() != 0:
        raise RuntimeError('Run on the authorized Linux Docker/SSH validation host')
    if run('systemctl', 'is-active', '--quiet', 'rmon-agent', check=False).returncode == 0:
        raise RuntimeError('This check must not stop an existing native agent service')
    prefix = 'rmon-stack-test-' + uuid4().hex[:12]
    root = Path(tempfile.mkdtemp(prefix=prefix + '-', dir='/tmp'))
    source = Path(args.source).resolve()
    agent_name = prefix + '-agent'
    agent_root = root / 'agent'
    project = ['docker', 'compose', '--project-name', prefix, '--project-directory', str(source),
               '-f', str(source / 'compose.yaml'), '-f', str(source / 'compose.server.yaml')]
    password = secrets.token_urlsafe(24)
    ports = {key: free_port(args.bind_ip) for key in ('web', 'server', 'agent')}
    origin = f'http://{args.bind_ip}:{ports["web"]}'
    environment = {**{key: value for key, value in os.environ.items() if not key.startswith('RMON_')},
                   'RMON_WEB_IMAGE': args.web_image, 'RMON_PROXY_IMAGE': args.proxy_image,
                   'RMON_SERVER_IMAGE': args.server_image, 'RMON_AGENT_IMAGE': args.agent_image,
                   'RMON_BIND_IP': args.bind_ip, 'RMON_WEB_PORT': str(ports['web']),
                   'RMON_SERVER_BIND_IP': args.bind_ip, 'RMON_SERVER_PORT': str(ports['server']),
                   'RMON_PUBLIC_URL': origin, 'RMON_AGENT_CONTROL_URL': origin,
                   'RMON_COOKIE_SECURE': '0', 'RMON_PROXY_SCHEME': 'http',
                   'RMON_SERVER_TOKEN_FILE': str(root / 'server-token')}
    for key, folder in [('CONFIG', 'config'), ('DATA', 'data'), ('LOG', 'logs'), ('TLS', 'tls')]:
        path = root / folder
        path.mkdir()
        environment[f'RMON_{key}_SOURCE'] = str(path)
    for name, value in [('password', password), ('server-token', secrets.token_urlsafe(32))]:
        path = root / name
        path.write_text(value)
        path.chmod(0o600)
        os.chown(path, 33, 33)
    mounts = sum((['-v', f'{root / name}:{target}'] for name, target in
                  [('config', '/etc/rmon'), ('data', '/var/lib/rmon'), ('logs', '/var/log/rmon')]), [])
    database = root / 'data/rmon.db'
    cookies = http.cookiejar.CookieJar()
    opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(cookies))

    def compose(*commands, **kwargs):
        return run(*project, *commands, env=environment, **kwargs)

    def container(service):
        return compose('ps', '-q', service).stdout.strip()

    def execute(service, code):
        return run('docker', 'exec', '-i', '--user', '33:33', '-e', 'RMON_SCHEDULER_ENABLED=0',
                   container(service), '/opt/rmon-venv/bin/python', '-', input=code).stdout

    def sql(statement, parameters=()):
        with closing(sqlite3.connect(database)) as connection:
            with connection:
                return connection.execute(statement, parameters).fetchall()

    def ready(*services):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            states = []
            for service in services:
                name = container(service)
                if not name:
                    raise AssertionError(service + ' was not created')
                state = json.loads(run('docker', 'inspect', name).stdout)[0]['State']
                if not state['Running']:
                    raise AssertionError(service + ' exited')
                states.append(state.get('Health', {}).get('Status') == 'healthy')
            if all(states):
                return
            time.sleep(3)
        raise AssertionError('Services did not become healthy: ' + ', '.join(services))

    def request(path, payload=None, *, form=False, method=None, expected=200):
        headers = {'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'}
        for cookie in cookies:
            if cookie.name == 'csrf_access_token':
                headers['X-CSRF-TOKEN'] = cookie.value
        data = (urlencode(payload) if form else json.dumps(payload)).encode() if payload is not None else None
        with opener.open(Request(origin + path, data=data, headers=headers, method=method), timeout=40) as response:
            assert response.status == expected, (path, response.status)
            return json.load(response)

    def login():
        assert request('/login', {'login': 'admin', 'pass': password})['status'] == 'done'

    def isolate_job(task_id):
        # Only the test target's paths/name change. Product defaults remain intact.
        overrides = {'agent_container_name': agent_name, 'agent_config_path': str(agent_root / 'rmon-agent.cfg'),
                     'agent_data_path': str(agent_root / 'data'), 'agent_log_path': str(agent_root / 'logs'),
                     'agent_lock_path': str(root / 'agent-lock'), 'agent_bind_ip': args.bind_ip,
                     'agent_image': args.agent_image, 'agent_pull': 'never'}
        execute('web', f'''
import json
from cryptography.fernet import Fernet
from app.modules.db.db_model import OperationJob
from app.modules.server.ssh import _get_fernet_key
job = OperationJob.get_by_id({task_id})
assert job.status == 'queued'
codec = Fernet(_get_fernet_key())
payload = json.loads(codec.decrypt(job.payload.encode()))
host = payload['inventory']['server']['hosts'][{args.ssh_host!r}]
host.update({overrides!r})
job.payload = codec.encrypt(json.dumps(payload).encode()).decode()
job.save()
''')

    def wait_task(task_id):
        deadline = time.monotonic() + 480
        while time.monotonic() < deadline:
            status = request(f'/api/v1.0/rmon/task-status/{task_id}')['status']
            if status == 'completed':
                return
            if status == 'failed':
                raise AssertionError(f'Agent operation {task_id} failed; inspect operations logs')
            time.sleep(3)
        raise AssertionError('Agent operation did not complete')

    def fresh_result(check_id, previous):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            rows = sql('SELECT h.rowid,h.status FROM smon_history h JOIN smon s ON s.id=h.smon_id '
                       'WHERE s.multi_check_id=? AND h.rowid>? ORDER BY h.rowid DESC', (check_id, previous))
            if rows and rows[0][1] == 1:
                return rows[0][0]
            time.sleep(3)
        raise AssertionError('No fresh successful check result')

    def fingerprints():
        paths = [root / 'config/rmon.cfg', *(root / 'data/keys').glob('rmon-key*')]
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths if path.is_file()}

    try:
        # Upgrade a genuine database created by the previous container image.
        run('docker', 'run', '--rm', *mounts, '-v', f'{root / "password"}:/run/password:ro',
            '-e', 'RMON_ADMIN_PASSWORD_FILE=/run/password', args.previous_image, 'init')
        before = fingerprints()
        sql('CREATE TABLE readiness_marker (value TEXT)')
        sql('INSERT INTO readiness_marker VALUES (?)', (prefix,))
        migration = run('docker', 'run', '--rm', '--user', '33:33', *mounts,
                        '-e', 'RMON_SCHEDULER_ENABLED=0',
                        '--entrypoint', '/opt/rmon-venv/bin/python',
                        args.web_image, 'app/migrate.py', 'migrate')
        assert '20260916000000_add_operation_queue' in migration.stdout
        assert sql('SELECT value FROM readiness_marker') == [(prefix,)]
        assert before == fingerprints()
        print('Existing installation: migration preserved configuration, keys and data', flush=True)

        # Use only the already authorized host credential, with read-only source access.
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(args.ssh_source_config)
        with closing(sqlite3.connect(f'file:{args.ssh_source_db}?mode=ro', uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            credential = dict(connection.execute('SELECT c.* FROM cred c JOIN servers s ON s.cred_id=c.id '
                                                  'WHERE s.id=?', (args.ssh_server_id,)).fetchone())
        seed = root / 'seed.json'
        seed.write_text(json.dumps({'credential': credential, 'key': cfg['main']['secret_phrase']}))
        seed.chmod(0o600)
        os.chown(seed, 33, 33)
        seed_code = f'''
import json
from pathlib import Path
from cryptography.fernet import Fernet
from app.modules.db.db_model import Cred, Server, Setting
from app.modules.server.ssh import crypt_password
source = json.loads(Path('/run/seed.json').read_text())
old = source['credential']
codec = Fernet(source['key'].encode())
values = {{name: crypt_password(codec.decrypt(old[name].encode()).decode()).decode() if old[name] else None
          for name in ('private_key', 'password', 'passphrase')}}
cred = Cred.create(name='container-readiness-ssh', username=old['username'], key_enabled=old['key_enabled'],
                   group_id=1, **values)
Server.create(hostname='container-readiness', ip={args.ssh_host!r}, group_id='1', cred_id=cred.id)
for name, value in {{'master_ip': {args.bind_ip!r}, 'master_port': {str(ports['server'])!r}}}.items():
    Setting.update(value=value).where(Setting.param == name).execute()
'''
        run('docker', 'run', '--rm', '-i', '--user', '33:33', *mounts, '-v', f'{seed}:/run/seed.json:ro',
            '-e', 'RMON_SCHEDULER_ENABLED=0', '-e', 'RMON_PROMETHEUS_MULTIPROC_DIR=/tmp',
            '--entrypoint', '/opt/rmon-venv/bin/python',
            args.web_image, '-', input=seed_code)
        seed.unlink()
        compose('up', '-d', '--no-build', 'web', 'proxy', 'server', 'scheduler')
        ready('web', 'server', 'scheduler')
        login()
        server_id = sql('SELECT id FROM servers WHERE ip=?', (args.ssh_host,))[0][0]
        created = request('/api/v1.0/rmon/agent', {'name': 'Container readiness', 'server_id': server_id,
                          'port': ports['agent'], 'description': '', 'result_transport': 'http'}, expected=202)
        agent_id, task_id = created['id'], created['tasks_ids'][0]
        isolate_job(task_id)
        compose('restart', 'web')
        ready('web')
        login()
        assert request(f'/api/v1.0/rmon/task-status/{task_id}')['status'] == 'created'
        compose('up', '-d', '--no-build', 'operations')
        ready('operations')
        wait_task(task_id)
        print('Queued installation survived web restart and completed through operations/SSH/Ansible', flush=True)
        execute('operations', '''
import os, time
from pathlib import Path
root = Path('/var/www/rmon/app/scripts/ansible/artifacts')
old = root / 'readiness-old-artifact'
old.mkdir()
(root / 'readiness-recent-artifact').mkdir()
os.utime(old, (time.time() - 3 * 86400,) * 2)
''')
        compose('restart', 'operations')
        ready('operations')
        execute('operations', '''
from pathlib import Path
root = Path('/var/www/rmon/app/scripts/ansible/artifacts')
assert not (root / 'readiness-old-artifact').exists()
assert (root / 'readiness-recent-artifact').is_dir()
''')
        print('Operations restart cleaned old temporary artifacts and preserved recent files', flush=True)

        def add_check(name):
            return request('/api/v1.0/rmon/check/http', {'name': name, 'place': 'agent', 'entities': [agent_id],
                'url': origin + '/login', 'method': 'get', 'interval': 10, 'check_timeout': 3,
                'retries': 1, 'accepted_status_codes': [200]}, expected=201)['id']

        check_id = add_check('Container readiness HTTP')
        result_id = fresh_result(check_id, 0)
        print('Agent execution and RMON Server ingestion produced a fresh successful result', flush=True)
        identity = sql('SELECT uuid FROM smon_agents WHERE id=?', (agent_id,))[0][0]
        saved = fingerprints()
        compose('stop', 'operations')
        action = request('/rmon/agent/action/restart', {'agent_id': agent_id}, form=True, expected=202)
        isolate_job(action['task_id'])
        compose('up', '-d', '--no-build', '--force-recreate', 'web', 'proxy', 'server', 'scheduler', 'operations')
        ready('web', 'server', 'scheduler', 'operations')
        login()
        wait_task(action['task_id'])
        fresh_result(check_id, result_id)
        second_check = add_check('Container readiness after recreation')
        fresh_result(second_check, 0)
        assert sql('SELECT uuid FROM smon_agents WHERE id=?', (agent_id,)) == [(identity,)]
        assert fingerprints() == saved
        assert sql('SELECT value FROM readiness_marker') == [(prefix,)]
        print('Recreated services retained queued work, identity, secrets, history and new successful checks', flush=True)
        for service in ('web', 'scheduler', 'operations', 'server'):
            logs = compose('logs', '--no-color', service).stdout
            assert 'Traceback (most recent call last)' not in logs, service + ' has a traceback'
        print('Full container stack readiness: passed', flush=True)
    except Exception:
        report = Path('/tmp') / (prefix + '-failure.log')
        report.write_text(compose('logs', '--no-color', check=False).stdout)
        report.chmod(0o600)
        print('Validation failure log:', report, flush=True)
        raise
    finally:
        compose('down', '--remove-orphans', check=False, timeout=240)
        listed = run('docker', 'ps', '-a', '--filter', 'name=' + agent_name, '--format', '{{.Names}}', check=False)
        for name in listed.stdout.splitlines():
            if name == agent_name or name.startswith(agent_name + '-previous-'):
                run('docker', 'rm', '-f', name, check=False)
        assert root.parent == Path('/tmp') and root.name.startswith(prefix + '-') and not root.is_symlink()
        shutil.rmtree(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--bind-ip', required=True)
    parser.add_argument('--ssh-host', required=True)
    parser.add_argument('--ssh-source-config', required=True)
    parser.add_argument('--ssh-source-db', required=True)
    parser.add_argument('--ssh-server-id', type=int, required=True)
    parser.add_argument('--previous-image', required=True)
    parser.add_argument('--web-image', default='rmon-web:test')
    parser.add_argument('--proxy-image', default='rmon-proxy:test')
    parser.add_argument('--server-image', required=True)
    parser.add_argument('--agent-image', required=True)
    exercise(parser.parse_args())
