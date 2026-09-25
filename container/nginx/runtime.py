"""Nginx-only TLS setup. The web container has no access to the TLS volume."""
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import tempfile


def settings():
    scheme = os.getenv('RMON_PROXY_SCHEME', 'https')
    if scheme not in ('http', 'https'):
        raise ValueError('RMON_PROXY_SCHEME must be http or https')
    return scheme


def certificate_san(host):
    try:
        ipaddress.ip_address(host)
        return f'IP:{host}'
    except ValueError:
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]*', host):
            raise ValueError('RMON_TLS_NAME must be a hostname or IP address')
        return f'DNS:{host}'


def ensure_certificate(cert=Path('/etc/ssl/certs/rmon.crt'), key=Path('/etc/ssl/certs/rmon.key'),
                       store=Path('/etc/ssl/certs/rmon')):
    if cert.is_file() and key.is_file():
        return
    if cert.exists() or key.exists() or any((store / name).exists() for name in ('rmon.crt', 'rmon.key')):
        raise ValueError('Incomplete TLS key pair; restore it instead of generating new keys')
    if os.getenv('RMON_SELF_SIGNED', '1') != '1':
        raise ValueError('Mount rmon.crt and rmon.key at /etc/ssl/certs')
    host = os.getenv('RMON_TLS_NAME', 'localhost')
    san = certificate_san(host)
    store.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.tls-init-', dir=store) as temp:
        temp = Path(temp)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-nodes', '-days', '365',
                        '-subj', f'/CN={host}', '-addext', f'subjectAltName={san}',
                        '-keyout', str(temp / 'rmon.key'), '-out', str(temp / 'rmon.crt')],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        (temp / 'rmon.key').chmod(0o600)
        # Exclusive links: never replace existing certificate material.
        os.link(temp / 'rmon.key', store / 'rmon.key')
        os.link(temp / 'rmon.crt', store / 'rmon.crt')
    print('Created a self-signed RMON certificate. Explicitly trust it in your client.', flush=True)


def render(template):
    scheme = settings()
    tls = ('ssl_certificate /etc/ssl/certs/rmon.crt;\n'
           'ssl_certificate_key /etc/ssl/certs/rmon.key;\n'
           'ssl_protocols TLSv1.2 TLSv1.3;' if scheme == 'https' else '')
    for name, value in {'RMON_LISTENER': '8080 ssl' if scheme == 'https' else '8080',
                        'RMON_TLS_DIRECTIVES': tls}.items():
        template = template.replace('${' + name + '}', value)
    return template


if __name__ == '__main__':
    os.umask(0o077)
    if settings() == 'https':
        ensure_certificate()
    Path('/etc/nginx/conf.d/default.conf').write_text(render(Path('/opt/rmon-proxy/default.conf.template').read_text()))
    subprocess.run(['nginx', '-t'], check=True)
    os.execvp('nginx', ['nginx', '-g', 'daemon off;'])
