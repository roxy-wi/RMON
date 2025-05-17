from peewee import *
from app.modules.db.db_model import connect, SmonAgent

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add agent_id column to smon table
    field = ForeignKeyField(SmonAgent, field=SmonAgent.id, null=True, on_delete='RESTRICT')
    try:
        migrate(
            migrator.add_column('smon', 'agent_id', field),
        )
        print("Added agent_id column to smon table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: agent_id' or 'column "agent_id" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'agent_id\'")'):
            print('Column agent_id already exists in smon table')
        else:
            print(f"Error adding agent_id column: {e}")


def downgrade():
    # Remove agent_id column from smon table
    try:
        migrate(
            migrator.drop_column('smon', 'agent_id'),
        )
        print("Removed agent_id column from smon table")
    except Exception as e:
        print(f"Error removing agent_id column: {e}")
