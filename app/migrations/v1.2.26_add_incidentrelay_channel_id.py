from playhouse.migrate import *
from peewee import IntegerField
from app.modules.db.db_model import connect, Version

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add the incidentrelay_channel_id column to the smon_http_check table
    try:
        migrate(
            migrator.add_column('smon', 'incidentrelay_channel_id', IntegerField(null=True)),
        )
        print("Added incidentrelay_channel_id column to smon table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: incidentrelay_channel_id' or 'column "incidentrelay_channel_id" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'incidentrelay_channel_id\'")'):
            print('Column incidentrelay_channel_id already exists in smon table')
        else:
            print(f"Error adding incidentrelay_channel_id column: {e}")

    # Update version
    try:
        Version.update(version='1.2.26').execute()
        print("Updated version record to '1.2.26'")
    except Exception as e:
        print(f"Error updating version record: {e}")


def downgrade():
    # Remove the incidentrelay_channel_id column from the smon table
    try:
        migrate(
            migrator.drop_column('smon', 'incidentrelay_channel_id'),
        )
        print("Removed incidentrelay_channel_id column from smon table")
    except Exception as e:
        print(f"Error removing incidentrelay_channel_id column: {e}")

    # Update version
    try:
        Version.update(version='1.2.25').execute()
        print("Reverted version record to '1.2.25'")
    except Exception as e:
        print(f"Error reverting version record: {e}")
