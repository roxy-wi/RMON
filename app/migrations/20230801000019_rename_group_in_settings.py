from playhouse.migrate import *

from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Rename group column in settings table
    try:
        migrate(
            migrator.rename_column('settings', 'group', 'group_id'),
        )
        print("Renamed group column to group_id in settings table")
    except Exception as e:
        if e.args[0] == 'no such column: "group"' or 'column "group" does not exist' in str(e) or str(e) == '(1060, no such column: "group")':
            print("Column already renamed")
        elif e.args[0] == "'bool' object has no attribute 'sql'":
            print("Column already renamed")
        else:
            print(f"Error renaming column: {e}")


def downgrade():
    # Revert column rename in settings table
    try:
        migrate(
            migrator.rename_column('settings', 'group_id', 'group'),
        )
        print("Reverted column rename in settings table")
    except Exception as e:
        print(f"Error reverting column rename: {e}")
