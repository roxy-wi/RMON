import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('proxy_runtime', ROOT / 'container/nginx/runtime.py')
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


@pytest.mark.parametrize('scheme', ['http', 'https'])
def test_proxy_routes_http_and_websocket_and_hides_readiness(monkeypatch, scheme):
    monkeypatch.setenv('RMON_PROXY_SCHEME', scheme)
    monkeypatch.setenv('RMON_SOCKET_HOST', 'socket')
    result = proxy.render((ROOT / 'container/nginx/default.conf.template').read_text())
    assert 'http://web:8080' in result
    assert 'http://socket:8766' in result
    assert 'location ^~ /_rmon/ { return 404; }' in result
    assert '$http_upgrade' in result and '${RMON_' not in result
    assert ('listen 8080 ssl' in result) is (scheme == 'https')
    assert ('ssl_certificate_key' in result) is (scheme == 'https')


@pytest.mark.parametrize('key,value', [('SCHEME', 'ftp'), ('HOST', 'x;bad'), ('PORT', '0'), ('PORT', '65536')])
def test_proxy_rejects_configuration_injection(monkeypatch, key, value):
    env = 'RMON_PROXY_SCHEME' if key == 'SCHEME' else 'RMON_SOCKET_' + key
    monkeypatch.setenv(env, value)
    with pytest.raises(ValueError):
        proxy.settings()


@pytest.mark.parametrize('host,san', [('192.0.2.10', 'IP:192.0.2.10'), ('::1', 'IP:::1'), ('rmon.test', 'DNS:rmon.test')])
def test_self_signed_certificate_supports_ips_and_dns(host, san):
    assert proxy.certificate_san(host) == san


def test_existing_tls_key_is_never_replaced(tmp_path, monkeypatch):
    cert, key = tmp_path / 'rmon.crt', tmp_path / 'rmon.key'
    cert.write_text('existing certificate')
    key.write_text('existing key')
    run = Mock()
    monkeypatch.setattr(proxy.subprocess, 'run', run)
    proxy.ensure_certificate(cert, key, tmp_path / 'store')
    run.assert_not_called()
    assert key.read_text() == 'existing key'
    key.unlink()
    with pytest.raises(ValueError, match='Incomplete'):
        proxy.ensure_certificate(cert, key, tmp_path / 'store')
    run.assert_not_called()


@pytest.mark.parametrize('name', ['rmon.conf', 'rmon_deb.conf'])
def test_packaged_apache_proxies_to_unix_socket_and_keeps_tls_paths(name):
    text = (ROOT / 'config_other/httpd' / name).read_text()
    assert 'WSGIDaemonProcess' not in text and 'WSGIScriptAlias' not in text
    assert 'unix:/run/rmon/rmon.sock|http://localhost/' in text
    assert 'ws://localhost:8766/' in text
    assert '/etc/ssl/certs/rmon.key' in text
    assert 'RequestHeader set X-Forwarded-Proto "https"' in text


def test_systemd_units_are_owned_by_packaging_repository():
    assert not list((ROOT / 'config_other').rglob('*.service'))


def test_web_image_has_no_tls_volume_or_docker_socket():
    # This section-level assertion also works without an optional YAML parser.
    web = (ROOT / 'compose.yaml').read_text().split('  proxy:')[0]
    assert 'rmon-tls' not in web and 'ports:' not in web
    assert 'docker.sock' not in web
    dockerfile = (ROOT / 'Dockerfile').read_text()
    assert 'mod-wsgi' not in dockerfile and 'apache2' not in dockerfile


@pytest.mark.parametrize('enabled', [True, False])
def test_real_client_ip_trusts_only_one_hop_in_explicit_proxy_mode(monkeypatch, enabled):
    from flask import Flask, request
    from app.modules.common.proxy import configure_trusted_proxy
    app = Flask('proxy-regression-test')
    monkeypatch.setenv('RMON_PROXY_MODE', '1' if enabled else '0')
    configure_trusted_proxy(app)
    @app.get('/')
    def address():
        return {'ip': request.remote_addr, 'host': request.host, 'scheme': request.scheme}
    result = app.test_client().get('/', headers={'X-Forwarded-For': 'forged, 192.0.2.10',
        'X-Forwarded-Host': 'evil.test', 'X-Forwarded-Proto': 'https'}).json
    assert result == {'ip': '192.0.2.10' if enabled else '127.0.0.1', 'host': 'localhost', 'scheme': 'http'}
