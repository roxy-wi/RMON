from peewee import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add email_channel_id column to smon table
    try:
        migrate(
            migrator.add_column('smon', 'email_channel_id', IntegerField(null=True)),
        )
        print("Added email_channel_id column to smon table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: email_channel_id' or 'column "email_channel_id" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'email_channel_id\'")'):
            print('Column email_channel_id already exists in smon table')
        else:
            print(f"Error adding email_channel_id column: {e}")


def downgrade():
    # Remove email_channel_id column from smon table
    try:
        migrate(
            migrator.drop_column('smon', 'email_channel_id'),
        )
        print("Removed email_channel_id column from smon table")
    except Exception as e:
        print(f"Error removing email_channel_id column: {e}")
