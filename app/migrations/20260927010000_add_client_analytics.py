from peewee import BigIntegerField, BooleanField, CharField, IntegerField
from playhouse.migrate import migrate

from app.modules.client_telemetry.models import ClientDirtyInterval, ClientObservation, ClientSegment, ClientSegmentDimension, ClientRollup
from app.modules.db.db_model import conn, connect


def upgrade():
    migrator = connect(get_migrator=True)
    existing = {column.name for column in conn.get_columns('client_dirty_intervals')}
    fields = {'processed_generation': BigIntegerField(default=0), 'pending': BooleanField(default=True),
              'owner': CharField(max_length=32, null=True),
              'lease_until_us': BigIntegerField(default=0), 'available_us': BigIntegerField(default=0),
              'attempts': IntegerField(default=0), 'last_error': CharField(max_length=160, null=True),
              'last_received_us': BigIntegerField(default=0), 'updated_us': BigIntegerField(default=0),
              'raw_deleted': BooleanField(default=False)}
    for name, field in fields.items():
        if name not in existing:
            migrate(migrator.add_column('client_dirty_intervals', name, field))
    # Reconcile on every attempt, including a restart after partial MySQL DDL.
    ClientDirtyInterval.update(pending=ClientDirtyInterval.generation > ClientDirtyInterval.processed_generation).execute()
    tables = [ClientSegment, ClientSegmentDimension, ClientRollup]
    conn.create_tables(tables, safe=True)
    for model in [ClientDirtyInterval, ClientObservation, *tables]:
        present = {(tuple(index.columns), index.unique) for index in conn.get_indexes(model._meta.table_name)}
        required = [((field.column_name,), field.unique) for field in model._meta.sorted_fields
                    if not field.primary_key and (field.index or field.unique)]
        required.extend((tuple(model._meta.fields[name].column_name for name in fields), unique)
                        for fields, unique in model._meta.indexes)
        for columns, unique in required:
            if (columns, unique) not in present:
                migrate(migrator.add_index(model._meta.table_name, columns, unique=unique))


def downgrade():
    raise RuntimeError('Client aggregates are retained. Restore a database backup to reverse this migration.')
