from peewee import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add runbook column to multi_check table
    try:
        migrate(
            migrator.add_column('multi_check', 'runbook', TextField(null=True)),
        )
        print("Added runbook column to multi_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: runbook' or 'column "runbook" of relation "multi_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'runbook\'")'):
            print('Column runbook already exists in multi_check table')
        else:
            print(f"Error adding runbook column: {e}")


def downgrade():
    # Remove runbook column from multi_check table
    try:
        migrate(
            migrator.drop_column('multi_check', 'runbook'),
        )
        print("Removed runbook column from multi_check table")
    except Exception as e:
        print(f"Error removing runbook column: {e}")
