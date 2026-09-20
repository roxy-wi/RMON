import concurrent.futures
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from peewee import SqliteDatabase
from playhouse.migrate import SqliteMigrator

from app.modules.db.db_model import InstallationTasks, OperationJob, OperationLock, Server, conn
from app.modules.operations import queue
from app.modules.operations.worker import LeaseGuard, Worker


@pytest.fixture
def target(tmp_path, monkeypatch):
    monkeypatch.setenv('RMON_PROCESS_HEALTH_DIR', str(tmp_path))
    server = Server.create(hostname='operations-test', ip=f'{uuid4().hex}.test', group_id='1')
    yield server
    InstallationTasks.delete().where(InstallationTasks.server_id == server.server_id).execute()
    server.delete_instance()


def enqueue(target, action='install'):
    inventory = {'server': {'hosts': {target.ip: {'action': action, 'agent_uuid': str(uuid4()),
                                                'private_test_value': 'never-store-plaintext'}}}}
    return queue.enqueue(inventory, [target.ip], 'rmon_agent', 'Agent', action, 1)


def expire(task_id):
    OperationJob.update(lease_until=queue.database_time() - timedelta(seconds=1)).where(
        OperationJob.task == task_id).execute()


def test_enqueue_is_durable_encrypted_and_does_not_execute(target, monkeypatch):
    from app.modules.service import installation
    monkeypatch.setattr(installation.roxywi_common, 'get_jwt_token_claims', lambda: {'user_id': 1, 'group': 1})
    run = Mock(side_effect=AssertionError('Web executed the operation'))
    monkeypatch.setattr(installation, 'run_ansible', run)
    inventory = {'server': {'hosts': {target.ip: {'action': 'install', 'secret': 'test-only-secret'}}}}
    task_id = installation.run_ansible_thread(inventory, [target.ip], 'rmon_agent', 'Agent', 'install')
    assert InstallationTasks.get_by_id(task_id).status == 'created'
    assert 'test-only-secret' not in OperationJob.get_by_id(task_id).payload
    conn.close()
    claimed, owner = queue.claim()
    assert claimed == task_id
    assert queue.load_payload(claimed, owner)['inventory'] == inventory
    run.assert_not_called()


def test_empty_poll_is_one_select_without_writes(monkeypatch):
    execute = Mock(wraps=conn.execute_sql)
    monkeypatch.setattr(conn, 'execute_sql', execute)
    assert queue.claim() is None
    assert execute.call_count == 1
    assert execute.call_args.args[0].startswith('SELECT')


def test_concurrent_workers_claim_once_and_serialize_target(target):
    first, second = enqueue(target), enqueue(target)
    def claim():
        try:
            return queue.claim()
        finally:
            conn.close()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: claim(), range(6)))
    claimed = [result for result in results if result is not None]
    assert len(claimed) == 1 and claimed[0][0] == first
    assert OperationJob.get_by_id(first).attempts == 1
    assert queue.finish(*claimed[0])
    next_task = queue.claim()
    assert next_task[0] == second
    assert queue.finish(*next_task)


def test_expired_lease_cannot_renew_or_finish_and_is_recovered(target):
    task = enqueue(target)
    claim = queue.claim()
    expire(task)
    assert not queue.renew(*claim)
    callback = Mock()
    assert not queue.finish(*claim, on_success=callback)
    callback.assert_not_called()
    assert queue.recover_expired() == 1
    assert queue.claim() is None  # Recovery has a cooldown, no immediate retry loop.
    OperationJob.update(available_at=queue.database_time()).where(OperationJob.task == task).execute()
    replacement = queue.claim()
    assert replacement[0] == task and replacement[1] != claim[1]
    assert not queue.finish(*claim)
    assert queue.finish(*replacement)
    assert OperationJob.get_by_id(task).payload is None


def test_renew_accepts_an_unchanged_deadline_but_rejects_stale_owners(target, monkeypatch):
    task = enqueue(target)
    claimed = queue.claim()
    now = queue.database_time()
    monkeypatch.setattr(queue, 'database_time', lambda: now)
    assert queue.renew(*claimed)
    # Match MySQL's affected-row count for an update with the same values.
    monkeypatch.setattr(conn, 'rows_affected', lambda cursor: 0)
    assert queue.renew(*claimed)
    assert not queue.renew(task, 'another-owner')
    expire(task)
    assert not queue.renew(*claimed)


def test_repeated_crashes_are_bounded_and_release_target(target):
    task = enqueue(target)
    for _ in range(queue.MAX_ATTEMPTS):
        OperationJob.update(available_at=queue.database_time()).where(OperationJob.task == task).execute()
        assert queue.claim()[0] == task
        expire(task)
        assert queue.recover_expired() == 1
    assert queue.claim() is None
    assert InstallationTasks.get_by_id(task).status == 'failed'
    assert OperationJob.get_by_id(task).payload is None
    assert OperationLock.get_by_id(target.server_id).owner is None


def test_later_operation_cannot_overtake_a_delayed_retry(target):
    first, second = enqueue(target), enqueue(target)
    assert queue.claim()[0] == first
    expire(first)
    queue.recover_expired()
    assert queue.claim() is None
    assert OperationJob.get_by_id(second).status == 'queued'


def test_operations_for_other_servers_can_run_concurrently(target):
    other = Server.create(hostname='other-operations-test', ip=f'{uuid4().hex}.test', group_id='1')
    try:
        first, second = enqueue(target), enqueue(other)
        assert queue.claim()[0] == first
        assert queue.claim()[0] == second
    finally:
        InstallationTasks.delete().where(InstallationTasks.server_id == other.server_id).execute()
        other.delete_instance()


def test_changed_server_group_invalidates_old_operation(target):
    enqueue(target)
    claimed = queue.claim()
    Server.update(group_id='2').where(Server.server_id == target.server_id).execute()
    with pytest.raises(ValueError, match='group changed'):
        queue.load_payload(*claimed)


def test_control_api_returns_a_durable_task_and_removed_history_is_404(target, client, auth_headers):
    from app.modules.db.db_model import SmonAgent
    agent = SmonAgent.create(server_id=target.server_id, name='Queue API test', uuid=str(uuid4()),
                             description='', port=5101)
    try:
        response = client.post('/rmon/agent/action/start', data={'agent_id': agent.id}, headers=auth_headers(1, 1))
        assert response.status_code == 202
        task_id = response.json['task_id']
        status = client.get(f'/api/v1.0/rmon/task-status/{task_id}', headers=auth_headers(1, 1))
        assert status.status_code == 200 and status.json['status'] == 'created'
        assert 'payload' not in status.json and status.json['action'] == 'start'
        assert queue.finish(*queue.claim())
        InstallationTasks.update(finish_date=datetime.now() - timedelta(days=31)).where(
            InstallationTasks.id == task_id).execute()
        queue.cleanup()
        assert client.get(f'/api/v1.0/rmon/task-status/{task_id}', headers=auth_headers(1, 1)).status_code == 404
    finally:
        agent.delete_instance()


def test_cleanup_only_old_terminal_tasks_and_is_bounded(target):
    old = datetime.now() - timedelta(days=31)
    completed = enqueue(target)
    assert queue.finish(*queue.claim())
    failed = enqueue(target)
    assert queue.finish(*queue.claim(), error='test failure')
    recent = enqueue(target)
    assert queue.finish(*queue.claim())
    active = enqueue(target)
    pending = enqueue(target)
    queue.claim()
    InstallationTasks.update(finish_date=old).where(
        InstallationTasks.id.in_([completed, failed, active, pending])).execute()
    assert queue.cleanup(batch_size=1, max_batches=1) == 1
    assert queue.cleanup() == 1
    assert queue.cleanup() == 0
    assert {t.id for t in InstallationTasks.select().where(InstallationTasks.server_id == target.server_id)} == {
        recent, active, pending}
    assert not OperationJob.select().where(OperationJob.task.in_([completed, failed])).exists()


def test_new_worker_can_execute_saved_job_and_clears_sensitive_payload(target, monkeypatch):
    from app.modules.service import installation
    from app.modules.common import agent_transport
    task = enqueue(target)
    run = Mock(return_value=None)
    monkeypatch.setattr(installation, 'execute_installation', run)
    record = Mock()
    monkeypatch.setattr(agent_transport, 'record_applied', record)
    assert Worker().step()
    assert InstallationTasks.get_by_id(task).status == 'completed'
    assert OperationJob.get_by_id(task).payload is None
    run.assert_called_once()
    record.assert_called_once()


def test_worker_records_failure_without_leaking_payload(target, monkeypatch):
    from app.modules.service import installation
    enqueue(target)
    monkeypatch.setattr(installation, 'execute_installation', Mock(side_effect=ValueError('sensitive-material')))
    assert Worker().step()
    task = InstallationTasks.get(InstallationTasks.server_id == target.server_id)
    assert task.status == 'failed' and 'sensitive-material' not in task.error


def test_idle_worker_backs_off_and_recovery_is_not_run_each_poll(monkeypatch):
    worker = Worker()
    monkeypatch.setattr(queue, 'claim', Mock(return_value=None))
    recover = Mock()
    monkeypatch.setattr(queue, 'recover_expired', recover)
    cleanup = Mock()
    monkeypatch.setattr('app.jobs.delete_ansible_artifacts', cleanup)
    delays = []
    def wait(seconds, ready=True):
        delays.append(seconds)
        if len(delays) == 7:
            worker.stop()
    monkeypatch.setattr(worker, 'wait', wait)
    monkeypatch.setattr('runtime_health.pulse', Mock())
    monkeypatch.setattr('app.modules.operations.worker.random.uniform', lambda *_: 1)
    worker.run()
    assert delays == [2, 4, 8, 16, 30, 30, 30]
    assert recover.call_count == 1
    cleanup.assert_called_once_with()


def test_queue_migration_preserves_history_and_is_repeatable(tmp_path, monkeypatch):
    path = Path(__file__).parents[2] / 'app/migrations/20260916000000_add_operation_queue.py'
    spec = importlib.util.spec_from_file_location('operation_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    database = SqliteDatabase(tmp_path / 'old.db')
    monkeypatch.setattr(migration, 'connect', lambda get_migrator=False:
                        SqliteMigrator(database) if get_migrator else database)
    with database.connection_context():
        database.execute_sql('CREATE TABLE installation_tasks (id INTEGER PRIMARY KEY, status TEXT, finish_date DATETIME)')
        database.execute_sql("INSERT INTO installation_tasks VALUES (1, 'completed', '2026-01-01')")
        migration.upgrade()
        migration.upgrade()
        assert database.execute_sql('SELECT status FROM installation_tasks').fetchone() == ('completed',)
        assert {'operation_jobs', 'operation_locks'} <= set(database.get_tables())
        assert any(index.columns == ['status', 'finish_date'] for index in database.get_indexes('installation_tasks'))


def test_lease_guard_cancels_without_database_access_when_renewal_stalls(monkeypatch):
    clock = [0]
    monkeypatch.setattr('app.modules.operations.worker.time.monotonic', lambda: clock[0])
    guard = LeaseGuard()
    clock[0] = 100
    assert not guard.cancelled()
    guard.renewed()
    clock[0] = 220
    assert guard.cancelled()
    assert clock[0] < 100 + queue.LEASE_SECONDS


def test_rotation_preserves_queued_payload_and_can_be_repeated(target, monkeypatch):
    import os
    from cryptography.fernet import Fernet
    from rotate_credential_secret import rotate_credentials
    old = os.environ['RMON_SECRET_PHRASE']
    task_id = enqueue(target)
    monkeypatch.setenv('RMON_OLD_SECRET_PHRASE', old)
    monkeypatch.setenv('RMON_SECRET_PHRASE', Fernet.generate_key().decode())
    assert rotate_credentials() >= 1
    assert rotate_credentials() == 0
    claimed = queue.claim()
    assert claimed[0] == task_id
    assert queue.load_payload(*claimed)['inventory']['server']['hosts'][target.ip]['private_test_value'] == 'never-store-plaintext'


@pytest.mark.parametrize('runner_fails', [True, False])
def test_ansible_releases_ssh_agent_and_inventory_on_failure_or_success(tmp_path, monkeypatch, runner_fails):
    import sys
    from types import SimpleNamespace
    from app.modules.service import installation
    original_path = Path
    monkeypatch.setattr(installation, 'Path', lambda path: tmp_path if str(path).endswith('/ansible/inventory') else original_path(path))
    monkeypatch.setattr(installation, '_ensure_agent_collections', lambda: '/test/collections')
    monkeypatch.setattr(installation.sql, 'get_setting', lambda _: '')
    monkeypatch.setattr(installation.server_mod, 'start_ssh_agent', lambda: {'pid': 123, 'socket': 'test-socket'})
    stop = Mock()
    monkeypatch.setattr(installation.server_mod, 'stop_ssh_agent', stop)
    monkeypatch.setattr(installation, 'return_ssh_keys_path', lambda _: {
        'enabled': False, 'password': 'test-only-password', 'user': 'test', 'port': 22})
    cancelled = Mock(return_value=False)
    def execute(**kwargs):
        assert kwargs['cancel_callback'] is cancelled
        assert Path(kwargs['inventory']).is_file()
        if runner_fails:
            raise RuntimeError('Runner failed')
        return SimpleNamespace(rc=0, stats={'failures': {}, 'dark': {}})
    monkeypatch.setitem(sys.modules, 'ansible_runner', SimpleNamespace(run=execute))
    inventory = {'server': {'hosts': {'example.test': {'action': 'start'}}}}
    if runner_fails:
        with pytest.raises(RuntimeError, match='Runner failed'):
            installation.run_ansible(inventory, ['example.test'], 'rmon_agent', cancel_callback=cancelled)
    else:
        assert installation.run_ansible(inventory, ['example.test'], 'rmon_agent', cancel_callback=cancelled)['failures'] == {}
    stop.assert_called_once()
    assert not list(tmp_path.iterdir())
