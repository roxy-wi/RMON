from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable, pgsql_enable, Version

# Get the migrator for the current database
migrator = connect(get_migrator=True)

if pgsql_enable == '1':
    from playhouse.postgres_ext import BinaryJSONField as JSONField
elif mysql_enable == '1':
    from playhouse.mysql_ext import JSONField
else:
    from playhouse.sqlite_ext import JSONField


def upgrade():
    # Add body_json column to smon_http_check table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('smon_http_check', 'body_json', JSONField(null=True)),
            )
        else:
            migrate(
                migrator.add_column('smon_http_check', 'body_json', JSONField(null=True)),
            )
        print("Added body_json column to smon_http_check table")
    except Exception as e:
        print(e)
        if (e.args[0] == 'duplicate column name: body_json' or 'column "body_json" of relation "smon_http_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'body_json\'")'):
            print('Column body_json already exists in smon_http_check table')
        else:
            print(f"Error adding body_json column: {e}")

    # Update version
    try:
        Version.update(version='1.2.20').execute()
        print("Updated version record to '1.2.20'")
    except Exception as e:
        print(f"Error updating version record: {e}")


def downgrade():
    # Remove body_json column from smon_http_check table
    try:
        migrate(
            migrator.drop_column('smon_http_check', 'body_json'),
        )
        print("Removed body_json column from smon_http_check table")
    except Exception as e:
        print(f"Error removing body_json column: {e}")

    # Update version
    try:
        Version.update(version='1.2.19').execute()
        print("Reverted version record to '1.2.19'")
    except Exception as e:
        print(f"Error reverting version record: {e}")
