from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable, pgsql_enable

# Get the migrator for the current database
migrator = connect(get_migrator=True)

if pgsql_enable == '1':
    from playhouse.postgres_ext import BinaryJSONField as JSONField
elif mysql_enable == '1':
    from playhouse.mysql_ext import JSONField
else:
    from playhouse.sqlite_ext import JSONField


def upgrade():
    # Add auth column to smon_http_check table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('smon_http_check', 'auth', JSONField(null=True)),
            )
        else:
            migrate(
                migrator.add_column('smon_http_check', 'auth', JSONField(null=True)),
            )
        print("Added auth column to smon_http_check table")
    except Exception as e:
        print(e)
        if (e.args[0] == 'duplicate column name: auth' or 'column "auth" of relation "smon_http_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'auth\'")'):
            print('Column auth already exists in smon_http_check table')
        else:
            print(f"Error adding auth column: {e}")


def downgrade():
    # Remove auth column from smon_http_check table
    try:
        migrate(
            migrator.drop_column('smon_http_check', 'auth'),
        )
        print("Removed auth column from smon_http_check table")
    except Exception as e:
        print(f"Error removing auth column: {e}")
