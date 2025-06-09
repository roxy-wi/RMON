from peewee import *
from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add current_retries column to smon table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('smon', 'current_retries', IntegerField(default=0)),
                migrator.add_column_default('smon', 'current_retries', 0),
            )
        else:
            migrate(
                migrator.add_column('smon', 'current_retries', IntegerField(constraints=[SQL('DEFAULT 0')])),
                migrator.add_column_default('smon', 'current_retries', 0),
            )
        print("Added current_retries column to smon table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: current_retries' or 'column "current_retries" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'current_retries\'")'):
            print('Column current_retries already exists in smon table')
        else:
            print(f"Error adding current_retries column: {e}")


def downgrade():
    # Remove current_retries column from smon table
    try:
        migrate(
            migrator.drop_column('smon', 'current_retries'),
        )
        print("Removed current_retries column from smon table")
    except Exception as e:
        print(f"Error removing current_retries column: {e}")
