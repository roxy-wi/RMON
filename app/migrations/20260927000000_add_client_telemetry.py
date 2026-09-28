from app.modules.client_telemetry.models import CLIENT_TABLES
from playhouse.migrate import migrate

from app.modules.db.db_model import conn, connect


def upgrade():
    # Safe to resume after partially completed DDL, including on MySQL.
    conn.create_tables([model for model in CLIENT_TABLES if not conn.table_exists(model._meta.table_name)], safe=True)
    # On MySQL, Peewee skips indexes if a table already exists. Repair missing
    # indexes after interrupted DDL instead of accepting an incomplete schema.
    migrator = connect(get_migrator=True)
    for model in CLIENT_TABLES:
        table = model._meta.table_name
        available = {column.name for column in conn.get_columns(table)}
        present = {(tuple(index.columns), index.unique) for index in conn.get_indexes(table)}
        required = [((field.column_name,), field.unique) for field in model._meta.sorted_fields
                    if not field.primary_key and (field.index or field.unique)]
        required.extend((tuple(model._meta.fields[name].column_name for name in fields), unique)
                        for fields, unique in model._meta.indexes)
        for columns, unique in required:
            if set(columns) <= available and (columns, unique) not in present:
                migrate(migrator.add_index(table, columns, unique=unique))
                present.add((columns, unique))


def downgrade():
    raise RuntimeError('Client observations are retained. Restore a database backup to reverse this migration.')
