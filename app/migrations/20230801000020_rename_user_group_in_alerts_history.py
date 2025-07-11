from playhouse.migrate import *

from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Rename user_group column in rmon_alerts_history table
    try:
        migrate(
            migrator.rename_column('rmon_alerts_history', 'user_group', 'group_id'),
        )
        print("Renamed user_group column to group_id in rmon_alerts_history table")
    except Exception as e:
        if e.args[0] == 'no such column: "user_group"' or 'column "user_group" does not exist' in str(e) or str(e) == '(1060, no such column: "user_group")':
            print("Column already renamed")
        elif e.args[0] == "'bool' object has no attribute 'sql'":
            print("Column already renamed")
        else:
            print(f"Error renaming column: {e}")


def downgrade():
    # Revert column rename in rmon_alerts_history table
    try:
        migrate(
            migrator.rename_column('rmon_alerts_history', 'group_id', 'user_group'),
        )
        print("Reverted column rename in rmon_alerts_history table")
    except Exception as e:
        print(f"Error reverting column rename: {e}")
