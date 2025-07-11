from playhouse.migrate import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Rename columns in servers table
    try:
        migrate(
            migrator.rename_column('servers', 'creds_id', 'cred_id'),
            migrator.rename_column('servers', 'desc', 'description'),
        )
        print("Renamed columns in servers table")
    except Exception as e:
        if e.args[0] == 'no such column: "creds_id"' or 'column "creds_id" does not exist' in str(e) or str(e) == '(1060, no such column: "creds_id")':
            print("Columns already renamed")
        elif e.args[0] == "'bool' object has no attribute 'sql'":
            print("Columns already renamed")
        else:
            print(f"Error renaming columns: {e}")


def downgrade():
    # Revert column renames in servers table
    try:
        migrate(
            migrator.rename_column('servers', 'cred_id', 'creds_id'),
            migrator.rename_column('servers', 'description', 'desc'),
        )
        print("Reverted column renames in servers table")
    except Exception as e:
        print(f"Error reverting column renames: {e}")
