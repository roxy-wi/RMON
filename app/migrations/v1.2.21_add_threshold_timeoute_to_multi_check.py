from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable, pgsql_enable, Version

if pgsql_enable == '1':
    from playhouse.postgres_ext import BinaryJSONField as JSONField
elif mysql_enable == '1':
    from playhouse.mysql_ext import JSONField
else:
    from playhouse.sqlite_ext import JSONField

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add proxy column to smon_http_check table
    try:
        migrate(
            migrator.add_column('smon_http_check', 'proxy', JSONField(null=True)),
        )
        print("Added proxy column to smon_http_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: proxy' or 'column "proxy" of relation "smon_http_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'proxy\'")'):
            print('Column proxy already exists in smon_http_check table')
        else:
            print(f"Error adding proxy column: {e}")

    # Update version
    try:
        Version.update(version='1.2.21').execute()
        print("Update version record to '1.2.21'")
    except Exception as e:
        print(f"Error reverting version record: {e}")


def downgrade():
    # Remove proxy column from smon_http_check table
    try:
        migrate(
            migrator.drop_column('smon_http_check', 'proxy'),
        )
        print("Removed proxy column from smon_http_check table")
    except Exception as e:
        print(f"Error removing proxy column: {e}")

    # Update version
    try:
        Version.update(version='1.2.20').execute()
        print("Reverted version record to '1.2.20'")
    except Exception as e:
        print(f"Error reverting version record: {e}")
