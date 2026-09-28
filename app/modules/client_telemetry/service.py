"""Authenticated management of client projects, definitions and sending keys."""
import hashlib
import secrets
from datetime import datetime, timezone

from peewee import MySQLDatabase, PostgresqlDatabase, SQL, Select, fn

from app.modules.db.db_model import ActionHistory, conn
from app.modules.client_telemetry.models import (
    ClientCheck, ClientDefinition, ClientKey, ClientProject,
)
from app.modules.client_telemetry.schemas import Definition


class TelemetryError(Exception):
    def __init__(self, status, code, message, details=None, retry_after=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details, self.retry_after = details, retry_after


def database_us():
    if isinstance(conn, MySQLDatabase):
        expression = fn.UTC_TIMESTAMP()
    elif isinstance(conn, PostgresqlDatabase):
        # Lease checks must see elapsed time even inside a transaction waiting
        # for a project lock; CURRENT_TIMESTAMP is fixed at transaction start.
        expression = fn.timezone('UTC', fn.clock_timestamp())
    else:
        expression = SQL('CURRENT_TIMESTAMP')
    value = conn.execute(Select(columns=[expression])).fetchone()[0]
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp()) * 1000000


def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def audit(actor, action):
    ActionHistory.create(service='client', user_id=actor, action=action)


def lock_project(project_id):
    """First statement inside a transaction: serialize writes without SELECT FOR UPDATE.

    A real revision increment obtains a write lock on SQLite/MySQL/PostgreSQL and
    gives consistent affected-row semantics. No network calls run under this lock.
    """
    if ClientProject.update(revision=ClientProject.revision + 1).where(ClientProject.id == project_id).execute() != 1:
        raise TelemetryError(404, 'project_not_found', 'Project was not found')
    return ClientProject.get_by_id(project_id)


def create_project(body, group_id, actor):
    with conn.atomic():
        project = ClientProject.create(**body.model_dump(exclude={'group_id'}), group=group_id, created_us=database_us())
        audit(actor, f'Created client project {project.id}')
    return project


def set_project_state(project_id, enabled, actor):
    with conn.atomic():
        lock_project(project_id)
        ClientProject.update(enabled=enabled).where(ClientProject.id == project_id).execute()
        audit(actor, f'Set client project {project_id} enabled={enabled}')


def create_check(project_id, body, actor):
    with conn.atomic():
        lock_project(project_id)
        if ClientCheck.select().where((ClientCheck.project == project_id) & (ClientCheck.code == body.code)).exists():
            raise TelemetryError(409, 'check_exists', 'A check with this code already exists')
        check = ClientCheck.create(project=project_id, code=body.code, name=body.name, description=body.description)
        ClientDefinition.create(check=check.id, version=1, definition=body.definition.model_dump(), created_us=database_us())
        audit(actor, f'Created client check {check.id} in project {project_id}')
    return check


def add_definition(project_id, check_id, definition, actor, *, expected_version=None):
    with conn.atomic():
        lock_project(project_id)
        check = ClientCheck.get_or_none((ClientCheck.id == check_id) & (ClientCheck.project == project_id))
        if check is None:
            raise TelemetryError(404, 'check_not_found', 'Check was not found')
        if expected_version is not None and check.current_version != expected_version:
            raise TelemetryError(409, 'definition_changed', 'The definition has changed; reload it before saving')
        if check.current_version >= 100:
            raise TelemetryError(409, 'version_limit', 'Create a new check after 100 definition versions')
        for row in ClientDefinition.select().where(ClientDefinition.check == check_id):
            old = Definition.model_validate(row.definition)
            incompatible = old.has_outcome != definition.has_outcome
            for name in old.metrics.keys() & definition.metrics.keys():
                before, after = old.metrics[name], definition.metrics[name]
                incompatible |= (before.type, before.unit) != (after.type, after.unit)
            for name in old.context.keys() & definition.context.keys():
                incompatible |= old.context[name].type != definition.context[name].type
            if incompatible:
                raise TelemetryError(409, 'incompatible_definition', 'Use a new field or check code for a changed type, unit or outcome')
        version = check.current_version + 1
        ClientDefinition.create(check=check_id, version=version, definition=definition.model_dump(), created_us=database_us())
        ClientCheck.update(current_version=version).where(ClientCheck.id == check_id).execute()
        audit(actor, f'Created definition {version} for client check {check_id}')
    return version


def issue_key(project_id, body, actor):
    token = 'rmon_pub_' + secrets.token_urlsafe(32)
    with conn.atomic():
        lock_project(project_id)
        codes = {row.code for row in ClientCheck.select(ClientCheck.code).where(
            (ClientCheck.project == project_id) & ClientCheck.code.in_(body.checks))}
        if codes != set(body.checks):
            raise TelemetryError(422, 'unknown_checks', 'Every allowed check must belong to this project')
        key = ClientKey.create(project=project_id, token_hash=token_hash(token), prefix=token[:16],
                               created_us=database_us(), **body.model_dump())
        audit(actor, f'Issued client key {key.id} for project {project_id}')
    return key, token


def revoke_key(project_id, key_id, actor):
    with conn.atomic():
        lock_project(project_id)
        key = ClientKey.get_or_none((ClientKey.id == key_id) & (ClientKey.project == project_id))
        if key is None:
            raise TelemetryError(404, 'key_not_found', 'Key was not found')
        if not key.revoked:
            ClientKey.update(revoked=True).where(ClientKey.id == key_id).execute()
            audit(actor, f'Revoked client key {key_id} for project {project_id}')
