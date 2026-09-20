"""Explicit initialization and Gunicorn entrypoint; never migrate on restart."""
import argparse
import configparser
import getpass
import os
from pathlib import Path
import secrets
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
UID = GID = 33  # Ubuntu's www-data; existing data must already be accessible to it.


def read_config(path=None):
    path = Path(path or os.getenv('RMON_CONFIG_FILE', '/etc/rmon/rmon.cfg'))
    cfg = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    with path.open(encoding='utf-8') as stream:
        cfg.read_file(stream)
    for section, keys in {'main': ('lib_path', 'log_path', 'secret_phrase'),
                          'mysql': ('enable',), 'pgsql': ('enable',)}.items():
        for key in keys:
            cfg.get(section, key)
    if cfg['mysql']['enable'] not in ('0', '1') or cfg['pgsql']['enable'] not in ('0', '1'):
        raise ValueError('Database enable flags must be 0 or 1')
    if cfg['mysql']['enable'] == cfg['pgsql']['enable'] == '1':
        raise ValueError('Enable only one database backend')
    return cfg


def option(cfg, name, default=''):
    return os.getenv('RMON_' + name.upper(), cfg.get('container', name, fallback=default))






def prepare_directory(path):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Runtime directories must use absolute paths')
    path.mkdir(parents=True, exist_ok=True)
    # No recursive chown of user data. Empty newly mounted volumes can be initialized.
    if not any(path.iterdir()):
        os.chown(path, UID, GID)
        path.chmod(0o750)


def drop_privileges():
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(GID)
        os.setuid(UID)


def private_file(path, data, owner=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    if owner:
        os.chown(path, UID, GID)


def ensure_new_config(path):
    if path.exists():
        return
    from cryptography.fernet import Fernet
    data = (ROOT / 'config_other/rmon.cfg').read_text(encoding='utf-8')
    private_file(path, data.replace('CHANGE_ME', Fernet.generate_key().decode()).encode())


def database(cfg):
    """Preflight without importing app (which requires the JWT keys first)."""
    from peewee import MySQLDatabase, PostgresqlDatabase, SqliteDatabase
    if cfg['pgsql']['enable'] == '1':
        section = cfg['pgsql']
        return PostgresqlDatabase(section['db'], user=section['user'], password=section['password'],
                                  host=section['host'], port=int(section['port']), connect_timeout=5)
    if cfg['mysql']['enable'] == '1':
        section = cfg['mysql']
        return MySQLDatabase(section['mysql_db'], user=section['mysql_user'], password=section['mysql_password'],
                             host=section['mysql_host'], port=int(section['mysql_port']), connect_timeout=5)
    return SqliteDatabase(os.getenv('RMON_DB_PATH', '/var/lib/rmon/rmon.db'))


def require_empty_database(cfg):
    db = database(cfg)
    try:
        if db.get_tables():
            raise ValueError('init requires an empty database; existing installations must use serve')
    finally:
        db.close()


def jwt_keys():
    if os.getenv('RMON_JWT_ALGORITHM', 'RS256') != 'RS256':
        return
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    private = Path(os.getenv('RMON_JWT_PRIVATE_KEY_FILE', '/var/lib/rmon/keys/rmon-key'))
    public = Path(os.getenv('RMON_JWT_PUBLIC_KEY_FILE', '/var/lib/rmon/keys/rmon-key.pub'))
    if private.exists() and public.exists():
        return
    if private.exists() or public.exists():
        raise ValueError('Incomplete JWT key pair; restore the missing key (no automatic rotation)')
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_file(private, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    private_file(public, key.public_key().public_bytes(serialization.Encoding.PEM,
                                                      serialization.PublicFormat.SubjectPublicKeyInfo))




def admin_password():
    filename = os.getenv('RMON_ADMIN_PASSWORD_FILE')
    if filename:
        password = Path(filename).read_text(encoding='utf-8').rstrip('\r\n')
    elif sys.stdin.isatty():
        password = getpass.getpass('Initial admin password (at least 12 characters): ')
        if password != getpass.getpass('Confirm password: '):
            raise ValueError('Passwords do not match')
    else:
        raise ValueError('Use an interactive init or mount RMON_ADMIN_PASSWORD_FILE')
    if len(password) < 12:
        raise ValueError('Initial admin password must contain at least 12 characters')
    return password


def initialize_schema(password):
    from werkzeug.security import generate_password_hash
    from app import create_db
    from app.modules.db.db_model import (BaseModel, conn, User, Role, Setting, UserGroups,
                                        Migration, Version, RoxyTool)
    from app.modules.db.migrations import get_migration_files
    from app.version import get_service_version
    # Check again under the application identity; never baseline an existing schema.
    if conn.get_tables():
        raise ValueError('Refusing to initialize a nonempty database')
    with conn.atomic():
        conn.create_tables(BaseModel.__subclasses__())
        create_db.default_values()
        if read_config()['pgsql']['enable'] == '1':
            # The explicit Default group id must advance the sequence in this transaction.
            conn.execute_sql("SELECT setval(pg_get_serial_sequence('groups', 'id'), (SELECT max(id) FROM groups))")
        if (User.select().count() != 3 or Role.select().count() != 4 or
                UserGroups.select().count() != 3 or not Setting.select().exists()):
            raise RuntimeError('Default database values were not initialized completely')
        User.update(password=generate_password_hash(password)).where(User.username == 'admin').execute()
        User.update(enabled=0, password=None).where(User.username != 'admin').execute()
        RoxyTool.update(current_version='0').execute()
        Version.insert(version=get_service_version()).execute()
        for name in get_migration_files():
            Migration.create(name=name[:-3])
    conn.close()


def check_application():
    from cryptography.fernet import Fernet
    cfg = read_config()
    Fernet((os.getenv('RMON_SECRET_PHRASE') or cfg['main']['secret_phrase']).encode('ascii'))
    from app import app
    from app.modules.db.db_model import Setting
    with app.app_context():
        if not Setting.select().limit(1).exists():
            raise ValueError('Database is not initialized')
    for path in (cfg['main']['lib_path'], cfg['main']['log_path']):
        if not os.access(path, os.W_OK):
            raise ValueError(f'{path} must be writable by www-data (uid 33)')


def healthcheck():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    token = Path('/tmp/rmon-health-token').read_text().strip()
    request = urllib.request.Request('http://127.0.0.1:8080/_rmon/ready', headers={'X-RMON-Health-Token': token})
    with opener.open(request, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError('RMON is not ready')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('serve', 'init', 'check', 'healthcheck', 'scheduler', 'operations'), default='serve', nargs='?')
    parser.add_argument('--role', choices=('scheduler', 'operations'))
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    command = args.command
    os.umask(0o077)
    if command == 'healthcheck':
        if args.role:
            import runtime_health
            if not runtime_health.healthy(args.role, ready=not args.live):
                raise RuntimeError('Process is not ready')
            return
        healthcheck()
        return
    if command == 'check':
        os.environ['RMON_SCHEDULER_ENABLED'] = '0'
        drop_privileges()
        check_application()
        return
    if os.getuid() != 0:
        raise ValueError('Entrypoint must start as root; Gunicorn runs the application as www-data')
    password = admin_password() if command == 'init' else None
    config_path = Path(os.getenv('RMON_CONFIG_FILE', '/etc/rmon/rmon.cfg'))
    if command == 'init':
        ensure_new_config(config_path)
    cfg = read_config(config_path)
    for path in (cfg['main']['lib_path'], cfg['main']['log_path'], '/var/lib/rmon/keys',
                 os.getenv('RMON_PROMETHEUS_MULTIPROC_DIR', '/tmp/rmon-prometheus')):
        prepare_directory(path)
    if command == 'init':
        require_empty_database(cfg)
        jwt_keys()
        # Preflight SQLite was opened as root; only this verified empty database is new.
        if cfg['mysql']['enable'] == cfg['pgsql']['enable'] == '0':
            os.chown(os.getenv('RMON_DB_PATH', '/var/lib/rmon/rmon.db'), UID, GID)
        os.environ['RMON_SCHEDULER_ENABLED'] = '0'
        drop_privileges()
        initialize_schema(password)
        print('Initialized. Login: admin. Default editor/guest accounts are disabled.')
        return
    for key in ('public_url', 'cookie_secure'):
        if cfg.has_option('container', key):
            os.environ.setdefault('RMON_' + key.upper(), cfg['container'][key])
    subprocess.run([sys.executable, '-m', 'container.runtime', 'check'], check=True, timeout=30)
    if command in ('scheduler', 'operations'):
        drop_privileges()
        os.execv(sys.executable, [sys.executable, str(ROOT / f'{command}_runner.py')])
    os.environ['RMON_SCHEDULER_ENABLED'] = '0'
    token = secrets.token_urlsafe(32)
    # Ephemeral probe credential only; never part of persistent application secrets.
    token_path = Path('/tmp/rmon-health-token')
    token_path.unlink(missing_ok=True)
    private_file(token_path, token.encode())
    os.environ['RMON_HEALTH_TOKEN'] = token
    os.execv('/opt/rmon-venv/bin/gunicorn', ['gunicorn', '--config', '/var/www/rmon/gunicorn.conf.py',
                                           'container.wsgi:application'])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never print connection strings, passwords, tokens or key material.
        print(f'RMON container {type(exc).__name__}: startup failed. Check configuration, mounts and database access.', file=sys.stderr)
        if isinstance(exc, (ValueError, FileNotFoundError, PermissionError)):
            print(str(exc), file=sys.stderr)
        sys.exit(1)
