"""Exercise the real certificate tasks using temporary files and the web identity."""
import configparser
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ssl
import threading


@contextmanager
def receiver(mode, certificate, key, ca):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(401)
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    if mode != 'http':
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, key)
        if mode == 'mtls':
            context.load_verify_locations(ca)
            context.verify_mode = ssl.CERT_REQUIRED
        server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run(role):
    role = Path(role).resolve()
    with tempfile.TemporaryDirectory(prefix='rmon-agent-tls-test-') as directory:
        root = Path(directory)
        ca, ca_key = root / 'issuer.crt', root / 'issuer.key'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
                        '-subj', '/CN=Temporary test issuer', '-addext', 'basicConstraints=critical,CA:TRUE',
                        '-keyout', str(ca_key), '-out', str(ca)], check=True, capture_output=True)
        targets = [root / 'existing-paths' / name for name in ('trust.pem', 'client.pem', 'private.pem')]
        config = root / 'agent.cfg'
        config.write_text('[master]\nscheme = http\n[untouched]\nsetting = keep-me\n')
        options = dict(zip(('master.ca_file', 'master.client_cert', 'master.client_key'), map(str, targets)))
        variables = {'ansible_python_interpreter': sys.executable, 'agent_existing_options': options,
                     'agent_config_path': str(config), 'agent_mtls_enabled': True,
                     'agent_uuid': '181a769d-ecf2-4f2a-a7a4-f47800a745a1',
                     'agent_tls_ca_file': str(ca), 'agent_tls_ca_key_file': str(ca_key),
                     'agent_certificate_directory': str(root / 'issued')}
        playbook = root / 'test.json'
        playbook.write_text(json.dumps([{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
            'vars_files': [str(role / 'defaults/main.yml')],
            'tasks': [{'ansible.builtin.include_tasks': str(role / 'tasks/tls.yml')}]}]))

        def apply(**overrides):
            return subprocess.run(['ansible-playbook', '-i', 'localhost,', str(playbook), '-e',
                                   json.dumps({**variables, **overrides})], capture_output=True, text=True, timeout=120)

        first = apply()
        assert first.returncode == 0, first.stdout + first.stderr
        cfg = configparser.ConfigParser()
        cfg.read(config)
        assert cfg['master']['scheme'] == 'https' and cfg['master']['tls_verify'] == 'true'
        assert cfg['untouched']['setting'] == 'keep-me'
        assert [cfg['master'][key] for key in ('ca_file', 'client_cert', 'client_key')] == list(map(str, targets))
        assert targets[2].stat().st_mode & 0o777 == 0o600
        assert sorted(path.name for path in targets[0].parent.iterdir()) == sorted(path.name for path in targets)
        snapshots = {path: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) for path in targets}
        second = apply()
        assert second.returncode == 0, second.stdout + second.stderr
        assert snapshots == {path: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns) for path in targets}
        print('mTLS generation, original paths, private key permissions and repeat without rotation: passed', flush=True)

        targets[2].unlink()
        incomplete = apply()
        assert incomplete.returncode != 0 and 'pair is incomplete' in incomplete.stdout
        assert not targets[2].exists() and hashlib.sha256(targets[1].read_bytes()).hexdigest() == snapshots[targets[1]][0]
        print('Incomplete existing pair is preserved and rejected: passed', flush=True)

        issued = Path(variables['agent_certificate_directory']) / variables['agent_uuid']
        copied = apply(agent_tls_generate=False, agent_tls_cert_file=str(issued / 'agent.crt'), agent_tls_key_file=str(issued / 'agent.key'))
        assert copied.returncode == 0, copied.stdout + copied.stderr
        assert hashlib.sha256(targets[2].read_bytes()).hexdigest() == snapshots[targets[2]][0]
        wrong = apply(agent_tls_cert_file=str(issued / 'agent.crt'), agent_tls_key_file=str(ca_key))
        assert wrong.returncode != 0 and 'does not match' in wrong.stdout
        print('Supplied certificate copying and mismatched key rejection: passed', flush=True)

        server_key, server_cert, csr = (root / name for name in ('server.key', 'server.crt', 'server.csr'))
        extensions = root / 'server.ext'
        extensions.write_text('subjectAltName=IP:127.0.0.1\nextendedKeyUsage=serverAuth\n')
        subprocess.run(['openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=Test receiver',
                        '-keyout', str(server_key), '-out', str(csr)], check=True, capture_output=True)
        subprocess.run(['openssl', 'x509', '-req', '-in', str(csr), '-CA', str(ca), '-CAkey', str(ca_key),
                        '-CAcreateserial', '-days', '2', '-extfile', str(extensions), '-out', str(server_cert)],
                       check=True, capture_output=True)
        for mode in ('http', 'https', 'mtls'):
            with receiver(mode, server_cert, server_key, ca) as port:
                checked = apply(agent_transport=mode, agent_mtls_enabled=mode == 'mtls',
                                agent_tls_cert_file=str(issued / 'agent.crt'),
                                agent_tls_key_file=str(issued / 'agent.key'),
                                agent_verify_result_connection=True, master_ip='127.0.0.1', master_port=port)
                assert checked.returncode == 0, checked.stdout + checked.stderr
                print(f'{mode}: verified result-server connection through Ansible passed', flush=True)
        with receiver('https', server_cert, server_key, ca) as port:
            rejected = apply(agent_transport='mtls', agent_mtls_enabled=True,
                             agent_verify_result_connection=True, master_ip='127.0.0.1', master_port=port)
            assert rejected.returncode != 0 and 'must require a trusted client certificate' in rejected.stdout
            print('mTLS selection rejects a server without mandatory client authentication: passed', flush=True)


if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / 'app/scripts/ansible/roles/rmon_agent')
