"""Durable agent operations. Empty polls are a single indexed read, never a write."""
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from cryptography.fernet import Fernet
from peewee import MySQLDatabase, PostgresqlDatabase, SQL, Select, fn

from app.modules.db.db_model import InstallationTasks, OperationJob, OperationLock, Server, conn
from app.modules.server.ssh import _get_fernet_key

LEASE_SECONDS = 180
MAX_ATTEMPTS = 3
RETENTION_DAYS = 30


def clock_expression():
    if isinstance(conn, MySQLDatabase):
        return fn.UTC_TIMESTAMP()
    if isinstance(conn, PostgresqlDatabase):
        return fn.timezone('UTC', SQL('CURRENT_TIMESTAMP'))
    return SQL('CURRENT_TIMESTAMP')


def database_time():
    value = conn.execute(Select(columns=[clock_expression()])).fetchone()
    now = value[0]
    if isinstance(now, str):
        now = datetime.fromisoformat(now)
    if now.tzinfo:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    return now


def enqueue(inventory, server_ips, role, service_name, action, user_id):
    if role != 'rmon_agent' or action not in {'install', 'delete', 'reconfigure', 'start', 'stop', 'restart'}:
        raise ValueError('Unsupported agent operation')
    if len(server_ips) != 1 or set(inventory.get('server', {}).get('hosts', {})) != set(server_ips):
        raise ValueError('An agent operation must target exactly one server')
    server = Server.get(Server.ip == server_ips[0])
    payload = Fernet(_get_fernet_key()).encrypt(json.dumps({
        'inventory': inventory, 'server_ips': server_ips, 'role': role,
    }, separators=(',', ':')).encode()).decode()
    with conn.atomic():
        OperationLock.insert(server=server.server_id).on_conflict_ignore().execute()
        task = InstallationTasks.create(service_name=service_name, server_id=server.server_id,
                                        user_id=user_id, group_id=server.group_id, action=action)
        OperationJob.create(task=task.id, server=server.server_id, payload=payload, available_at=database_time())
    return task.id


def claim():
    earlier = OperationJob.alias()
    preceding = earlier.select(SQL('1')).where(
        (earlier.server == OperationJob.server) & (earlier.task < OperationJob.task)
        & earlier.status.in_(('queued', 'running')))
    candidates = list(OperationJob.select(OperationJob.task, OperationJob.server)
                      .join(OperationLock, on=(OperationJob.server == OperationLock.server))
                      .where((OperationJob.status == 'queued') & (OperationJob.available_at <= clock_expression())
                             & OperationLock.owner.is_null() & ~fn.EXISTS(preceding))
                      .order_by(OperationJob.task).limit(16).dicts())
    for candidate in candidates:
        owner = uuid4().hex
        with conn.atomic() as transaction:
            locked = OperationLock.update(owner=owner).where(
                (OperationLock.server == candidate['server']) & OperationLock.owner.is_null()).execute()
            if not locked:
                continue
            now = database_time()
            updated = OperationJob.update(status='running', owner=owner,
                                          lease_until=now + timedelta(seconds=LEASE_SECONDS),
                                          attempts=OperationJob.attempts + 1).where(
                (OperationJob.task == candidate['task']) & (OperationJob.status == 'queued')
                & (OperationJob.available_at <= now)).execute()
            if not updated:
                transaction.rollback()
                continue
            InstallationTasks.update(status='running', error=None).where(
                InstallationTasks.id == candidate['task']).execute()
        return candidate['task'], owner
    return None


def renew(task_id, owner):
    now = database_time()
    deadline = now + timedelta(seconds=LEASE_SECONDS)
    changed = OperationJob.update(lease_until=deadline).where(
        (OperationJob.task == task_id) & (OperationJob.owner == owner)
        & (OperationJob.status == 'running') & (OperationJob.lease_until > now)).execute() == 1
    if changed:
        return True
    # MySQL reports zero affected rows when the deadline is already the same.
    return OperationJob.select().where(
        (OperationJob.task == task_id) & (OperationJob.owner == owner)
        & (OperationJob.status == 'running') & (OperationJob.lease_until >= deadline)
        & (OperationJob.lease_until > clock_expression())).exists()


def load_payload(task_id, owner):
    job = OperationJob.get((OperationJob.task == task_id) & (OperationJob.owner == owner)
                          & (OperationJob.status == 'running') & (OperationJob.lease_until > clock_expression()))
    if str(job.task.group_id_id) != str(job.server.group_id):
        raise ValueError('The server group changed; submit the operation again')
    return json.loads(Fernet(_get_fernet_key()).decrypt(job.payload.encode()))


def finish(task_id, owner, error=None, on_success=None):
    with conn.atomic():
        now = database_time()
        status = 'failed' if error else 'completed'
        changed = OperationJob.update(status=status, payload=None, owner=None, lease_until=None).where(
            (OperationJob.task == task_id) & (OperationJob.owner == owner)
            & (OperationJob.status == 'running') & (OperationJob.lease_until > now)).execute()
        if not changed:
            return False
        if not error and on_success:
            on_success()
        InstallationTasks.update(status=status, error=error, finish_date=datetime.now()).where(
            InstallationTasks.id == task_id).execute()
        OperationLock.update(owner=None).where(OperationLock.owner == owner).execute()
    return True


def recover_expired(limit=100):
    expired = list(OperationJob.select(OperationJob.task, OperationJob.owner, OperationJob.attempts)
                   .where((OperationJob.status == 'running') & (OperationJob.lease_until <= clock_expression()))
                   .order_by(OperationJob.lease_until).limit(limit).dicts())
    recovered = 0
    for job in expired:
        with conn.atomic():
            now = database_time()
            failed = job['attempts'] >= MAX_ATTEMPTS
            changed = OperationJob.update(
                status='failed' if failed else 'queued', owner=None, lease_until=None,
                available_at=now + timedelta(seconds=30),
                **({'payload': None} if failed else {}),
            ).where((OperationJob.task == job['task']) & (OperationJob.owner == job['owner'])
                    & (OperationJob.status == 'running') & (OperationJob.lease_until <= now)).execute()
            if not changed:
                continue
            InstallationTasks.update(
                status='failed' if failed else 'created',
                error='Operation interrupted repeatedly. Check the agent and try again.' if failed else None,
                finish_date=datetime.now(),
            ).where(InstallationTasks.id == job['task']).execute()
            OperationLock.update(owner=None).where(OperationLock.owner == job['owner']).execute()
            recovered += 1
    return recovered


def cleanup(batch_size=500, max_batches=20):
    """Bound each daily cleanup; pending operations are never removed."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    active = OperationJob.select(OperationJob.task).where(OperationJob.status.in_(('queued', 'running')))
    eligible = ((InstallationTasks.status.in_(('completed', 'failed')))
                & (InstallationTasks.finish_date < cutoff) & InstallationTasks.id.not_in(active))
    deleted = 0
    for _ in range(max_batches):
        ids = [row.id for row in InstallationTasks.select(InstallationTasks.id).where(eligible)
               .order_by(InstallationTasks.finish_date).limit(batch_size)]
        if not ids:
            break
        deleted += InstallationTasks.delete().where(eligible & InstallationTasks.id.in_(ids)).execute()
        if len(ids) < batch_size:
            break
    return deleted
