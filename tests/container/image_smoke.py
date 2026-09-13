"""Run against locally built web/proxy images; owns only uniquely named test resources."""
import base64
import http.cookiejar
import json
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid


def docker(*args, check=True):
    return subprocess.run(['docker', *args], text=True, capture_output=True, check=check, timeout=90)


def wait_ready(name):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        state = json.loads(docker('inspect', name).stdout)[0]['State']
        if state.get('Health', {}).get('Status') == 'healthy':
            return
        if not state['Running']:
            raise AssertionError('Container exited: ' + docker('logs', name).stderr)
        time.sleep(2)
    raise AssertionError('Container not ready: ' + docker('logs', name).stderr)


def request(opener, url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    return opener.open(urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}), timeout=30)


def exercise(scheme):
    prefix = 'rmon-smoke-' + uuid.uuid4().hex[:12]
    network = prefix + '-network'
    web, proxy = (prefix + '-' + component for component in ('web', 'proxy'))
    volumes = [prefix + '-' + name for name in ('config', 'data', 'logs', 'tls')]
    mounts = sum((['-v', name + ':' + path] for name, path in zip(volumes[:3],
                  ('/etc/rmon', '/var/lib/rmon', '/var/log/rmon'))), [])
    port = 8080
    password = secrets.token_urlsafe(24)
    try:
        docker('network', 'create', network)
        with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
            temporary = Path(temporary)
            password_file = temporary / 'password'
            password_file.write_text(password)
            password_file.chmod(0o600)
            init = [*mounts, '-v', f'{password_file}:/run/password:ro', '-e', 'RMON_ADMIN_PASSWORD_FILE=/run/password']
            docker('run', '--rm', *init, 'rmon-web:test', 'init')
            assert docker('run', '--rm', *init, 'rmon-web:test', 'init', check=False).returncode != 0
            snapshots = []
            for _ in range(2):
                docker('run', '-d', '--name', web, '--network', network, '--network-alias', 'web',
                       '--security-opt', 'no-new-privileges:true', *mounts,
                       '-e', 'RMON_COOKIE_SECURE=' + ('1' if scheme == 'https' else '0'), 'rmon-web:test')
                wait_ready(web)
                docker('run', '-d', '--name', proxy, '--network', network, '-p', f'127.0.0.1::{port}',
                       '-e', f'RMON_PROXY_SCHEME={scheme}',
                       '-e', 'RMON_TLS_NAME=127.0.0.1', '-v', f'{volumes[3]}:/etc/ssl/certs/rmon', 'rmon-proxy:test')
                mapped = int(docker('port', proxy, str(port)).stdout.strip().split(':')[-1])
                deadline = time.monotonic() + 60
                while True:
                    result = docker('exec', proxy, 'nginx', '-t', check=False)
                    cert_ready = scheme == 'http' or docker('exec', proxy, 'test', '-f', '/etc/ssl/certs/rmon.crt', check=False).returncode == 0
                    if result.returncode == 0 and cert_ready:
                        break
                    if time.monotonic() > deadline:
                        raise AssertionError(docker('logs', proxy).stderr)
                    time.sleep(1)
                context = ssl.create_default_context()
                if scheme == 'https':
                    cert = temporary / 'rmon.crt'
                    docker('cp', f'{proxy}:/etc/ssl/certs/rmon/rmon.crt', str(cert))
                    context.load_verify_locations(cafile=str(cert))
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                    urllib.request.HTTPSHandler(context=context),
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                origin = f'{scheme}://127.0.0.1:{mapped}'
                # The proxy may still be opening its listener immediately after nginx -t.
                while True:
                    try:
                        with request(opener, origin + '/login') as response:
                            assert response.status == 200
                        break
                    except (urllib.error.URLError, ConnectionError):
                        if time.monotonic() > deadline:
                            raise
                        time.sleep(1)
                with request(opener, origin + '/login', {'login': 'admin', 'pass': password}) as response:
                    assert json.load(response)['status'] == 'done'
                    cookies = response.headers.get_all('Set-Cookie') or []
                    assert any('access_token_cookie=' in value for value in cookies)
                    assert any('Secure' in value for value in cookies) is (scheme == 'https')
                with request(opener, origin + '/admin') as response:
                    assert response.status == 200
                try:
                    request(opener, origin + '/_rmon/ready')
                    raise AssertionError('Public readiness must be blocked')
                except urllib.error.HTTPError as error:
                    assert error.code == 404
                with socket.create_connection(('127.0.0.1', mapped), timeout=10) as raw:
                    connection = context.wrap_socket(raw, server_hostname='127.0.0.1') if scheme == 'https' else raw
                    with connection:
                        key = base64.b64encode(secrets.token_bytes(16)).decode()
                        connection.sendall((f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{mapped}\r\nUpgrade: websocket\r\n'
                                            f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
                        status = connection.recv(4096).split(b'\r\n', 1)[0]
                        assert status.split()[1] in (b'200', b'302'), status
                docker('exec', web, '/opt/rmon-venv/bin/python', '-c', 'import ldap, ansible_runner')
                # Agent installation runs under the web identity, including Ansible's temporary files.
                docker('exec', '--user', '33:33', web, 'ansible-playbook', '--syntax-check',
                       '/var/www/rmon/app/scripts/ansible/roles/rmon_agent.yml', '-i', 'localhost,')
                if scheme == 'http' and not snapshots:
                    docker('cp', str(Path(__file__).with_name('agent_tls_smoke.py')), f'{web}:/tmp/agent_tls_smoke.py')
                    subprocess.run(['docker', 'exec', '--user', '33:33', web, '/opt/rmon-venv/bin/python',
                                    '/tmp/agent_tls_smoke.py', '/var/www/rmon/app/scripts/ansible/roles/rmon_agent'],
                                   check=True, timeout=600)
                snapshot = docker('exec', web, '/opt/rmon-venv/bin/python', '-c',
                    "from pathlib import Path; import hashlib,json; "
                    "paths=[Path('/etc/rmon/rmon.cfg'), *Path('/var/lib/rmon/keys').glob('*')]; "
                    "print(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}))").stdout
                snapshots.append(json.loads(snapshot))
                # Prove the healthcheck checks the DB, not just an open HTTP port.
                sql = "import sqlite3; db=sqlite3.connect('/var/lib/rmon/rmon.db'); db.execute(%r); db.commit(); db.close()"
                docker('exec', web, '/opt/rmon-venv/bin/python', '-c', sql % 'ALTER TABLE settings RENAME TO settings_outage')
                try:
                    assert docker('exec', web, '/opt/rmon-venv/bin/python', '-m', 'container.runtime', 'healthcheck', check=False).returncode != 0
                finally:
                    docker('exec', web, '/opt/rmon-venv/bin/python', '-c', sql % 'ALTER TABLE settings_outage RENAME TO settings')
                docker('exec', web, '/opt/rmon-venv/bin/python', '-m', 'container.runtime', 'healthcheck')
                for name in (proxy, web):
                    docker('stop', '--time', '30', name)
                    docker('rm', name)
            assert snapshots[0] == snapshots[1], 'Application secrets or config changed after recreation'
            print(scheme + ': web-only proxy, login, readiness, DB outage and persistence passed')
    finally:
        for name in (proxy, web):
            docker('rm', '-f', name, check=False)
        docker('network', 'rm', network, check=False)
        for name in volumes:
            docker('volume', 'rm', name, check=False)


if __name__ == '__main__':
    for mode in ('http', 'https'):
        exercise(mode)
