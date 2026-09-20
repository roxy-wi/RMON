"""Exercise the real queue against disposable, private PostgreSQL/MariaDB containers."""
import argparse
import concurrent.futures
from datetime import datetime, timedelta
import importlib.util
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4


def inside(backend):
    root = Path('/tmp/rmon-queue-contract')
    root.mkdir()
    (root / 'prometheus').mkdir()
    config = root / 'rmon.cfg'
    config.write_text(f'''[main]
lib_path = {root}
log_path = {root}
secret_phrase = E2nCq8NnECvPQ5zUQntL_-Nt-qBncYkrEmMkYGzVpyM=
[mysql]
enable = {int(backend == 'mysql')}
mysql_host = database
mysql_port = 3306
mysql_user = root
mysql_password =
mysql_db = rmon_queue_test
[pgsql]
enable = {int(backend == 'postgres')}
host = database
port = 5432
user = rmon_test
password =
db = rmon_queue_test
''')
    os.environ.update(RMON_TESTING='1', RMON_SCHEDULER_ENABLED='0', RMON_CONFIG_FILE=str(config),
                      RMON_SECRET_KEY='queue-contract-test-only-secret-key-32-chars',
                      RMON_JWT_ALGORITHM='HS256', RMON_JWT_SECRET_KEY='queue-contract-test-only-jwt-key-32-chars',
                      RMON_PROMETHEUS_MULTIPROC_DIR=str(root / 'prometheus'))
    from app.modules.db.db_model import Groups, User, Server, InstallationTasks, OperationJob, OperationLock, conn
    from app.modules.operations import queue
    assert conn.database == 'rmon_queue_test'
    deadline = time.monotonic() + 120
    while True:
        try:
            conn.connect(reuse_if_open=True)
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)
    assert not conn.get_tables(), 'Use a fresh disposable test database'
    conn.create_tables([Groups, User, Server, InstallationTasks])
    spec = importlib.util.spec_from_file_location('queue_migration',
            Path('/var/www/rmon/app/migrations/20260916000000_add_operation_queue.py'))
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.upgrade()
    migration.upgrade()
    group = Groups.create(name='Queue test')
    user = User.create(username='queue-test', email='queue@example.test', role='1', group_id=group.group_id)
    server = Server.create(hostname='queue-test', ip='192.0.2.10', group_id=str(group.group_id))
    inventory = {'server': {'hosts': {server.ip: {'action': 'start', 'secret': 'test-only-value'}}}}
    def enqueue():
        return queue.enqueue(inventory, [server.ip], 'rmon_agent', 'Agent', 'start', user.user_id)
    first, second = enqueue(), enqueue()
    assert 'test-only-value' not in OperationJob.get_by_id(first).payload
    def claim():
        try:
            return queue.claim()
        finally:
            conn.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        claims = [result for result in pool.map(lambda _: claim(), range(6)) if result]
    assert len(claims) == 1 and claims[0][0] == first
    assert queue.load_payload(*claims[0])['inventory'] == inventory
    assert queue.renew(*claims[0])
    assert queue.renew(*claims[0])
    assert queue.finish(*claims[0])
    previous = queue.claim()
    assert previous[0] == second
    OperationJob.update(lease_until=queue.database_time() - timedelta(seconds=1)).where(OperationJob.task == second).execute()
    assert not queue.renew(*previous)
    assert not queue.finish(*previous)
    third = enqueue()
    assert queue.recover_expired() == 1
    assert queue.claim() is None
    OperationJob.update(available_at=queue.database_time()).where(OperationJob.task == second).execute()
    replacement = queue.claim()
    assert replacement[0] == second and replacement[1] != previous[1]
    assert not queue.finish(*previous)
    assert queue.finish(*replacement)
    InstallationTasks.update(finish_date=datetime.now() - timedelta(days=31)).where(
        InstallationTasks.id.in_([first, second])).execute()
    assert queue.cleanup(batch_size=1) == 2
    assert not OperationJob.select().where(OperationJob.task.in_([first, second])).exists()
    assert queue.claim()[0] == third
    assert queue.cleanup() == 0
    assert OperationLock.get_by_id(server.server_id).owner
    try:
        migration.downgrade()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Rollback removed a running operation')
    print(f'{backend}: migration, concurrent claims, FIFO, leases, recovery and cleanup passed', flush=True)


def outside(image, source=None, selected_backend=None):
    def docker(*args, check=True, timeout=300):
        return subprocess.run(['docker', *args], check=check, capture_output=True, text=True, timeout=timeout)
    for backend, db_image in [('postgres', 'postgres:16-alpine'), ('mysql', 'mariadb:11.4')]:
        if selected_backend and backend != selected_backend:
            continue
        print(f'{backend}: starting database queue check', flush=True)
        name = 'rmon-queue-test-' + uuid4().hex[:12]
        database, client = name + '-db', name + '-client'
        try:
            docker('pull', db_image)
            docker('network', 'create', '--internal', name)
            env = (['-e', 'POSTGRES_HOST_AUTH_METHOD=trust', '-e', 'POSTGRES_USER=rmon_test', '-e', 'POSTGRES_DB=rmon_queue_test']
                   if backend == 'postgres' else ['-e', 'MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1', '-e', 'MARIADB_DATABASE=rmon_queue_test'])
            settings = (['-c', 'shared_buffers=16MB', '-c', 'max_connections=20'] if backend == 'postgres'
                        else ['--innodb-buffer-pool-size=32M', '--performance-schema=OFF', '--max-connections=20'])
            docker('run', '-d', '--name', database, '--network', name, '--network-alias', 'database',
                   '--memory', '192m', '--memory-swap', '384m', *env, db_image, *settings)
            mounts = ['-v', str(Path(__file__).resolve()) + ':/queue-smoke.py:ro']
            if source:
                mounts += ['-v', str(Path(source).resolve()) + ':/var/www/rmon:ro']
            result = docker('run', '--name', client, '--network', name, '--memory', '128m', '--memory-swap', '256m',
                            *mounts, '-e', 'PYTHONPATH=/var/www/rmon', '--entrypoint', 'python',
                            image, '/queue-smoke.py', '--inside', backend, check=False)
            print(result.stdout, end='', flush=True)
            if result.returncode:
                print(result.stderr, flush=True)
                raise RuntimeError(f'{backend} queue contract failed')
        finally:
            docker('rm', '-fv', client, database, check=False)
            docker('network', 'rm', name, check=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inside', choices=['postgres', 'mysql'])
    parser.add_argument('--image', default='rmon-web:test')
    parser.add_argument('--source')
    parser.add_argument('--backend', choices=['postgres', 'mysql'])
    args = parser.parse_args()
    inside(args.inside) if args.inside else outside(args.image, args.source, args.backend)
