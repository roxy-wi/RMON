import configparser
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet

from container import runtime


@pytest.fixture
def cfg():
    return runtime.read_config(runtime.ROOT / 'config_other/rmon.cfg')


@pytest.mark.parametrize('container,bind', [(True, '0.0.0.0:8080'), (False, 'unix:/run/rmon/rmon.sock')])
def test_gunicorn_has_one_worker_no_preload_and_no_tls(monkeypatch, container, bind):
    import runpy
    monkeypatch.setenv('RMON_CONTAINER', '1' if container else '0')
    config = runpy.run_path(str(runtime.ROOT / 'gunicorn.conf.py'))
    assert config['bind'] == bind
    assert config['workers'] == 1
    assert config['threads'] == 10
    assert config['preload_app'] is False
    assert config['max_requests'] == 0
    assert 'certfile' not in config and 'keyfile' not in config


def test_env_overrides_optional_config_without_rewriting_it(cfg, monkeypatch):
    cfg['container'] = {'public_url': 'https://old.test'}
    monkeypatch.setenv('RMON_PUBLIC_URL', 'https://new.test')
    assert runtime.option(cfg, 'public_url') == 'https://new.test'
    assert cfg['container']['public_url'] == 'https://old.test'


def test_missing_configuration_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        runtime.read_config(tmp_path / 'missing.cfg')


@pytest.mark.parametrize('mysql,pgsql', [('1', '1'), ('yes', '0'), ('0', 'false')])
def test_ambiguous_database_rejected(tmp_path, cfg, mysql, pgsql):
    cfg['mysql']['enable'], cfg['pgsql']['enable'] = mysql, pgsql
    path = tmp_path / 'rmon.cfg'
    with path.open('w') as stream:
        cfg.write(stream)
    with pytest.raises(ValueError):
        runtime.read_config(path)


def test_init_generates_fernet_only_for_new_config(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'chown', Mock(), raising=False)
    path = tmp_path / 'rmon.cfg'
    runtime.ensure_new_config(path)
    original = path.read_bytes()
    Fernet(runtime.read_config(path)['main']['secret_phrase'].encode())
    runtime.ensure_new_config(path)
    assert path.read_bytes() == original
    assert b'/var/lib/rmon' in original


def test_existing_config_is_never_rewritten_even_if_invalid(tmp_path, monkeypatch):
    path = tmp_path / 'rmon.cfg'
    path.write_text('existing config must stay untouched')
    runtime.ensure_new_config(path)
    assert path.read_text() == 'existing config must stay untouched'


def test_secret_file_never_overwrites_existing_file(tmp_path):
    path = tmp_path / 'secret'
    path.write_bytes(b'existing')
    with pytest.raises(FileExistsError):
        runtime.private_file(path, b'replacement', owner=False)
    assert path.read_bytes() == b'existing'


def test_jwt_keys_persist_and_partial_pair_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'chown', Mock(), raising=False)
    monkeypatch.setenv('RMON_JWT_ALGORITHM', 'RS256')
    private, public = tmp_path / 'key', tmp_path / 'key.pub'
    monkeypatch.setenv('RMON_JWT_PRIVATE_KEY_FILE', str(private))
    monkeypatch.setenv('RMON_JWT_PUBLIC_KEY_FILE', str(public))
    runtime.jwt_keys()
    before = (private.read_bytes(), public.read_bytes())
    runtime.jwt_keys()
    assert (private.read_bytes(), public.read_bytes()) == before
    public.unlink()
    with pytest.raises(ValueError, match='Incomplete JWT'):
        runtime.jwt_keys()
    assert private.read_bytes() == before[0]


def test_prepare_directory_never_recursively_chowns_user_data(tmp_path, monkeypatch):
    chown = Mock()
    monkeypatch.setattr(os, 'chown', chown, raising=False)
    empty = tmp_path / 'empty'
    runtime.prepare_directory(empty)
    chown.assert_called_once_with(empty, 33, 33)
    (empty / 'existing').write_text('data')
    chown.reset_mock()
    runtime.prepare_directory(empty)
    chown.assert_not_called()


@pytest.mark.parametrize('backend', ['mysql', 'pgsql'])
def test_database_uses_existing_config_fields(cfg, backend):
    cfg[backend]['enable'] = '1'
    db = runtime.database(cfg)
    assert db.database == 'rmon'
    assert db.connect_params['host'] == '127.0.0.1'
    assert db.connect_params['user'] == 'rmon'
    assert db.connect_params['port'] == (3306 if backend == 'mysql' else 5432)


def test_init_refuses_nonempty_database(cfg, tmp_path, monkeypatch):
    monkeypatch.setenv('RMON_DB_PATH', str(tmp_path / 'data.db'))
    runtime.require_empty_database(cfg)
    db = runtime.database(cfg)
    db.execute_sql('CREATE TABLE existing (value TEXT)')
    db.execute_sql("INSERT INTO existing VALUES ('unchanged')")
    with pytest.raises(ValueError, match='empty database'):
        runtime.require_empty_database(cfg)
    assert db.execute_sql('SELECT value FROM existing').fetchone() == ('unchanged',)
    db.close()


@pytest.mark.parametrize('password,valid', [('short', False), ('long-unique-test-password', True)])
def test_admin_password_file(tmp_path, monkeypatch, password, valid):
    path = tmp_path / 'password'
    path.write_text(password + '\n')
    monkeypatch.setenv('RMON_ADMIN_PASSWORD_FILE', str(path))
    if valid:
        assert runtime.admin_password() == password
    else:
        with pytest.raises(ValueError, match='12 characters'):
            runtime.admin_password()


def test_admin_password_requires_input(monkeypatch):
    monkeypatch.delenv('RMON_ADMIN_PASSWORD_FILE', raising=False)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    with pytest.raises(ValueError, match='interactive init'):
        runtime.admin_password()


def test_healthcheck_ignores_proxy_environment(monkeypatch):
    opener = Mock()
    response = Mock(status=200)
    opener.open.return_value.__enter__ = Mock(return_value=response)
    opener.open.return_value.__exit__ = Mock(return_value=False)
    build = Mock(return_value=opener)
    monkeypatch.setattr(runtime.urllib.request, 'build_opener', build)
    monkeypatch.setattr(runtime.Path, 'read_text', lambda _: 'local-health-secret')
    runtime.healthcheck()
    assert build.call_args.args[0].proxies == {}
    request = opener.open.call_args.args[0]
    assert request.full_url == 'http://127.0.0.1:8080/_rmon/ready'
    assert request.get_header('X-rmon-health-token') == 'local-health-secret'
    assert opener.open.call_args.kwargs['timeout'] == 5


def test_fresh_schema_login_disabled_defaults_and_baseline(tmp_path):
    cfg_path = tmp_path / 'rmon.cfg'
    cfg = runtime.read_config(runtime.ROOT / 'config_other/rmon.cfg')
    cfg['main']['lib_path'] = str(tmp_path)
    cfg['main']['log_path'] = str(tmp_path)
    with cfg_path.open('w') as stream:
        cfg.write(stream)
    env = {**os.environ, 'RMON_CONFIG_FILE': str(cfg_path), 'RMON_DB_PATH': str(tmp_path / 'fresh.db'),
           'RMON_SCHEDULER_ENABLED': '0'}
    code = '''
from container.runtime import initialize_schema
initialize_schema('fresh-container-test-password')
from app import app
from app.modules.db.db_model import User, Migration, BaseModel, conn
from app.modules.db.migrations import get_migration_files
from app.modules.roxywi import roxy
from werkzeug.security import check_password_hash
assert check_password_hash(User.get(User.username == 'admin').password, 'fresh-container-test-password')
assert all(not u.enabled and u.password is None for u in User.select().where(User.username != 'admin'))
assert set(m.name for m in Migration.select()) == set(n[:-3] for n in get_migration_files())
assert set(m._meta.table_name for m in BaseModel.__subclasses__()) <= set(conn.get_tables())
roxy.update_plan = lambda: None
client = app.test_client()
assert client.get('/login').status_code == 200
assert client.post('/login', json={'login':'admin','pass':'fresh-container-test-password'}).status_code == 200
assert client.post('/login', json={'login':'admin','pass':'admin'}).status_code == 401
try:
    initialize_schema('must-not-reset-this-password')
except ValueError:
    pass
else:
    raise AssertionError('Existing database was reinitialized')
assert check_password_hash(User.get(User.username == 'admin').password, 'fresh-container-test-password')
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=runtime.ROOT, env=env,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_package_bootstrap_baselines_only_a_new_database(tmp_path):
    env = {**os.environ, 'RMON_DB_PATH': str(tmp_path / 'package.db'), 'RMON_SCHEDULER_ENABLED': '0'}
    result = subprocess.run([sys.executable, '-m', 'app.create_db'], cwd=runtime.ROOT, env=env,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    code = '''
import runpy
from app.modules.db.db_model import Migration, Version, User
from app.modules.db.migrations import get_migration_files
from app.version import get_service_version
assert set(m.name for m in Migration.select()) == set(n[:-3] for n in get_migration_files())
assert Version.get().version == get_service_version()
User.update(password='must-stay-unchanged').where(User.username == 'admin').execute()
runpy.run_module('app.create_db', run_name='__main__')
assert User.get(User.username == 'admin').password == 'must-stay-unchanged'
assert Version.select().count() == 1
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=runtime.ROOT, env=env,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_container_health_checks_database_without_public_route(app, monkeypatch):
    from container.wsgi import application
    from app.modules.db.db_model import Setting
    monkeypatch.setenv('RMON_HEALTH_TOKEN', 'test-probe-token')
    env = {'PATH_INFO': '/_rmon/ready', 'HTTP_X_RMON_HEALTH_TOKEN': 'test-probe-token'}
    status = []
    assert b''.join(application(env, lambda value, headers: status.append(value))) == b'{"status":"ready"}'
    assert status == ['200 OK']
    monkeypatch.setattr(Setting, 'select', Mock(side_effect=RuntimeError('secret connection details')))
    status.clear()
    assert b''.join(application(env, lambda value, headers: status.append(value))) == b'{"status":"not_ready"}'
    assert status == ['503 Service Unavailable']


@pytest.mark.parametrize('token', ['', 'wrong-token'])
def test_readiness_is_not_public(monkeypatch, token):
    from container.wsgi import application
    monkeypatch.setenv('RMON_HEALTH_TOKEN', 'test-probe-token')
    status = []
    data = application({'PATH_INFO': '/_rmon/ready', 'HTTP_X_RMON_HEALTH_TOKEN': token},
                       lambda value, headers: status.append(value))
    assert status == ['404 Not Found']
    assert b'ready' not in b''.join(data)
