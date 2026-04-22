from playhouse.migrate import *
from peewee import BooleanField, CharField
from app.modules.db.db_model import connect, Version

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add the use_kernel_timestamp column to the smon_http_check table
    try:
        migrate(
            migrator.add_column('smon_ping_check', 'use_kernel_timestamp', BooleanField(default=True)),
        )
        print("Added use_kernel_timestamp column to smon_ping_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: use_kernel_timestamp' or 'column "use_kernel_timestamp" of relation "smon_ping_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'use_kernel_timestamp\'")'):
            print('Column use_kernel_timestamp already exists in smon_ping_check table')
        else:
            print(f"Error adding use_kernel_timestamp column: {e}")

    # Add the resole_to_ip column to the smon_http_check table
    try:
        migrate(
            migrator.add_column('smon_http_check', 'resole_to_ip', CharField(null=True)),
        )
        print("Added resole_to_ip column to smon_http_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: resole_to_ip' or 'column "resole_to_ip" of relation "smon_http_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'resole_to_ip\'")'):
            print('Column resole_to_ip already exists in smon_http_check table')
        else:
            print(f"Error adding resole_to_ip column: {e}")

    # Update version
    try:
        Version.update(version='1.2.25').execute()
        print("Updated version record to '1.2.25'")
    except Exception as e:
        print(f"Error updating version record: {e}")


def downgrade():
    # Remove the use_kernel_timestamp column from the smon_ping_check table
    try:
        migrate(
            migrator.drop_column('smon_ping_check', 'use_kernel_timestamp'),
        )
        print("Removed use_kernel_timestamp column from smon_ping_check table")
    except Exception as e:
        print(f"Error removing use_kernel_timestamp column: {e}")

    # Remove the resole_to_ip column from the smon_http_check table
    try:
        migrate(
            migrator.drop_column('smon_http_check', 'resole_to_ip'),
        )
        print("Removed resole_to_ip column from smon_http_check table")
    except Exception as e:
        print(f"Error removing resole_to_ip column: {e}")

    # Update version
    try:
        Version.update(version='1.2.24').execute()
        print("Reverted version record to '1.2.24'")
    except Exception as e:
        print(f"Error reverting version record: {e}")