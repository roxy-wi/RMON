from playhouse.migrate import *
from peewee import BooleanField, IntegerField
from app.modules.db.db_model import connect, mysql_enable, pgsql_enable, Version

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add the accept_cookies column to the smon_http_check table
    try:
        migrate(
            migrator.add_column('smon_http_check', 'accept_cookies', BooleanField(default=True)),
        )
        print("Added accept_cookies column to smon_http_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: accept_cookies' or 'column "accept_cookies" of relation "smon_http_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'accept_cookies\'")'):
            print('Column accept_cookies already exists in smon_http_check table')
        else:
            print(f"Error adding accept_cookies column: {e}")

    # Add the http_version column to the smon_http_check table
    try:
        migrate(
            migrator.add_column('smon_http_check', 'http_version', IntegerField(default=0)),
        )
        print("Added http_version column to smon_http_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: http_version' or 'column "http_version" of relation "smon_http_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'http_version\'")'):
            print('Column http_version already exists in smon_http_check table')
        else:
            print(f"Error adding http_version column: {e}")

    # Update version
    try:
        Version.update(version='1.2.24').execute()
        print("Updated version record to '1.2.24'")
    except Exception as e:
        print(f"Error updating version record: {e}")


def downgrade():
    # Remove the accept_cookies column from the smon_http_check table
    try:
        migrate(
            migrator.drop_column('smon_http_check', 'accept_cookies'),
        )
        print("Removed accept_cookies column from smon_http_check table")
    except Exception as e:
        print(f"Error removing accept_cookies column: {e}")

    # Remove the http_version column from the smon_http_check table
    try:
        migrate(
            migrator.drop_column('smon_http_check', 'http_version'),
        )
        print("Removed http_version column from smon_http_check table")
    except Exception as e:
        print(f"Error removing http_version column: {e}")

    # Update version
    try:
        Version.update(version='1.2.23.3').execute()
        print("Reverted version record to '1.2.23.3'")
    except Exception as e:
        print(f"Error reverting version record: {e}")