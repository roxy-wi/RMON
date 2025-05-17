from peewee import *
from playhouse.migrate import *
from app.modules.db.db_model import connect
from datetime import datetime

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add a last_modified column to the smon table
    migrate(
        migrator.add_column('smon', 'last_modified', DateTimeField(default=datetime.now)),
    )
    print("Added last_modified column to smon table")


def downgrade():
    # Remove the last_modified column from the smon table
    migrate(
        migrator.drop_column('smon', 'last_modified'),
    )
    print("Removed last_modified column from smon table")
