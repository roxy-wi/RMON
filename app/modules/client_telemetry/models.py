"""Portable tables; times on the ingestion path are integer UTC microseconds."""
from peewee import AutoField, BigAutoField, BigIntegerField, BooleanField, CharField, ForeignKeyField, IntegerField, MySQLDatabase, TextField

from app.modules.db.db_model import BaseModel, Groups, JSONField, conn


class ClientModel(BaseModel):
    class Meta:
        # Explicit transactional storage and full Unicode even when an older
        # installation's database defaults use another engine or charset.
        table_settings = ['ENGINE=InnoDB', 'DEFAULT CHARSET=utf8mb4', 'COLLATE=utf8mb4_bin'] if isinstance(conn, MySQLDatabase) else None


class ClientProject(ClientModel):
    id = AutoField()
    group = ForeignKeyField(Groups, on_delete='CASCADE')
    name = CharField(max_length=160)
    description = TextField(default='')
    enabled = BooleanField(default=True)
    revision = BigIntegerField(default=0)
    created_us = BigIntegerField()
    events_per_minute = IntegerField(default=6000)
    requests_per_minute = IntegerField(default=1200)
    bytes_per_minute = BigIntegerField(default=8 * 1024 * 1024)
    quota_minute = BigIntegerField(default=0)
    quota_events = IntegerField(default=0)
    quota_requests = IntegerField(default=0)
    quota_bytes = BigIntegerField(default=0)

    class Meta:
        table_name = 'client_projects'


class ClientCheck(ClientModel):
    id = AutoField()
    project = ForeignKeyField(ClientProject, on_delete='CASCADE')
    code = CharField(max_length=64)
    name = CharField(max_length=160)
    description = TextField(default='')
    current_version = IntegerField(default=1)

    class Meta:
        table_name = 'client_checks'
        indexes = ((('project', 'code'), True),)


class ClientDefinition(ClientModel):
    id = AutoField()
    check = ForeignKeyField(ClientCheck, on_delete='CASCADE')
    version = IntegerField()
    definition = JSONField()
    created_us = BigIntegerField()

    class Meta:
        table_name = 'client_definitions'
        indexes = ((('check', 'version'), True),)


class ClientKey(ClientModel):
    id = AutoField()
    project = ForeignKeyField(ClientProject, on_delete='CASCADE')
    name = CharField(max_length=160)
    token_hash = CharField(max_length=64, unique=True)
    prefix = CharField(max_length=16)
    checks = JSONField()
    environments = JSONField()
    origins = JSONField()
    allow_no_origin = BooleanField(default=True)
    revoked = BooleanField(default=False)
    created_us = BigIntegerField()
    last_used_us = BigIntegerField(null=True)

    class Meta:
        table_name = 'client_keys'


class ClientReceipt(ClientModel):
    id = BigAutoField()
    project = ForeignKeyField(ClientProject, on_delete='CASCADE')
    event_id = CharField(max_length=36)
    content_hash = CharField(max_length=64)
    received_us = BigIntegerField(index=True)

    class Meta:
        table_name = 'client_receipts'
        indexes = ((('project', 'event_id'), True),)


class ClientObservation(ClientModel):
    id = BigAutoField()
    project = ForeignKeyField(ClientProject, on_delete='CASCADE')
    check = ForeignKeyField(ClientCheck, on_delete='CASCADE')
    definition = ForeignKeyField(ClientDefinition, on_delete='CASCADE')
    event_id = CharField(max_length=36)
    observed_us = BigIntegerField(index=True)
    received_us = BigIntegerField()
    status = CharField(max_length=5, null=True)
    # Canonical validated event preserves units/version and exact context casing.
    event = JSONField()

    class Meta:
        table_name = 'client_observations'
        indexes = ((('project', 'event_id'), True), (('check', 'observed_us'), False),
                   (('project', 'received_us'), False), (('definition', 'observed_us', 'id'), False))


class ClientDirtyInterval(ClientModel):
    id = BigAutoField()
    definition = ForeignKeyField(ClientDefinition, on_delete='CASCADE')
    minute = BigIntegerField()
    generation = BigIntegerField(default=1)
    processed_generation = BigIntegerField(default=0)
    pending = BooleanField(default=True)
    owner = CharField(max_length=32, null=True)
    lease_until_us = BigIntegerField(default=0)
    available_us = BigIntegerField(default=0)
    attempts = IntegerField(default=0)
    last_error = CharField(max_length=160, null=True)
    last_received_us = BigIntegerField(default=0)
    updated_us = BigIntegerField(default=0)
    raw_deleted = BooleanField(default=False)

    class Meta:
        table_name = 'client_dirty_intervals'
        indexes = ((('definition', 'minute'), True), (('pending', 'minute', 'id'), False),
                   (('raw_deleted', 'minute', 'id'), False))


class ClientSegment(ClientModel):
    id = BigAutoField()
    definition = ForeignKeyField(ClientDefinition, on_delete='CASCADE')
    minute = BigIntegerField(index=True)
    signature = CharField(max_length=64)
    dimensions = JSONField()

    class Meta:
        table_name = 'client_segments'
        indexes = ((('definition', 'minute', 'signature'), True),)


class ClientSegmentDimension(ClientModel):
    id = BigAutoField()
    segment = ForeignKeyField(ClientSegment, on_delete='CASCADE')
    name = CharField(max_length=64)
    value_hash = CharField(max_length=64)

    class Meta:
        table_name = 'client_segment_dimensions'
        indexes = ((('segment', 'name'), True), (('name', 'value_hash', 'segment'), False))


class ClientRollup(ClientModel):
    segment = ForeignKeyField(ClientSegment, primary_key=True, on_delete='CASCADE')
    generation = BigIntegerField()
    algorithm = IntegerField(default=1)
    state = JSONField()

    class Meta:
        table_name = 'client_rollups'


CLIENT_TABLES = [ClientProject, ClientCheck, ClientDefinition, ClientKey, ClientReceipt,
                 ClientObservation, ClientDirtyInterval, ClientSegment, ClientSegmentDimension, ClientRollup]
