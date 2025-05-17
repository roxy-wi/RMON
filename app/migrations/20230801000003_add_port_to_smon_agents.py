from peewee import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add port column to smon_agents table
    try:
        migrate(
            migrator.add_column('smon_agents', 'port', IntegerField(default=5101)),
            migrator.add_column_default('smon_agents', 'port', 5101),
        )
        print("Added port column to smon_agents table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: port' or 'column "port" of relation "smon_agents" already exists'
                or str(e) == '(1060, "Duplicate column name \'port\'")'):
            print('Column port already exists in smon_agents table')
        else:
            print(f"Error adding port column: {e}")


def downgrade():
    # Remove port column from smon_agents table
    try:
        migrate(
            migrator.drop_column('smon_agents', 'port'),
        )
        print("Removed port column from smon_agents table")
    except Exception as e:
        print(f"Error removing port column: {e}")
