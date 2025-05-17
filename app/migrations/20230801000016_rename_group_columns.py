from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Rename group columns
    try:
        migrate(
            migrator.rename_column('smon_groups', 'user_group', 'group_id'),
            migrator.rename_column('smon', 'group_id', 'check_group_id'),
            migrator.rename_column('smon', 'user_group', 'group_id')
        )
        print("Renamed group columns")
    except Exception as e:
        if e.args[0] == 'no such column: "user_group"' or 'column "user_group" does not exist' in str(e) or str(e) == '(1060, no such column: "user_group")':
            print("Columns already renamed")
        elif e.args[0] == "'bool' object has no attribute 'sql'":
            print("Columns already renamed")
        else:
            print(f"Error renaming columns: {e}")


def downgrade():
    # Revert column renames
    try:
        migrate(
            migrator.rename_column('smon_groups', 'group_id', 'user_group'),
            migrator.rename_column('smon', 'check_group_id', 'group_id'),
            migrator.rename_column('smon', 'group_id', 'user_group')
        )
        print("Reverted column renames")
    except Exception as e:
        print(f"Error reverting column renames: {e}")
