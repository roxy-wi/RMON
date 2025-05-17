from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Rename desc column in smon_status_pages table
    try:
        migrate(
            migrator.rename_column('smon_status_pages', 'desc', 'description')
        )
        print("Renamed desc column to description in smon_status_pages table")
    except Exception as e:
        if e.args[0] == 'no such column: "desc"' or 'column "desc" does not exist' in str(e) or str(e) == '(1060, no such column: "desc")':
            print("Column already renamed")
        elif e.args[0] == "'bool' object has no attribute 'sql'":
            print("Column already renamed")
        else:
            print(f"Error renaming column: {e}")


def downgrade():
    # Revert column rename in smon_status_pages table
    try:
        migrate(
            migrator.rename_column('smon_status_pages', 'description', 'desc')
        )
        print("Reverted column rename in smon_status_pages table")
    except Exception as e:
        print(f"Error reverting column rename: {e}")
