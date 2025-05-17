from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Rename columns to standardize naming conventions
    try:
        migrate(
            migrator.rename_column('smon_agents', 'desc', 'description'),
            migrator.rename_column('smon', 'desc', 'description'),
            migrator.rename_column('smon_status_pages', 'style', 'custom_style'),
            migrator.rename_column('smon_status_pages', 'desc', 'description'),
            migrator.rename_column('telegram', 'groups', 'group_id'),
            migrator.rename_column('slack', 'groups', 'group_id'),
            migrator.rename_column('mattermost', 'groups', 'group_id'),
            migrator.rename_column('pd', 'groups', 'group_id'),
            migrator.rename_column('smon', 'en', 'enabled'),
            migrator.rename_column('servers', 'groups', 'group_id'),
            migrator.rename_column('servers', 'cred', 'cred_id'),
            migrator.rename_column('servers', 'enable', 'enabled'),
            migrator.rename_column('user', 'activeuser', 'enabled'),
            migrator.rename_column('user', 'groups', 'group_id'),
            migrator.rename_column('cred', 'enable', 'key_enabled'),
            migrator.rename_column('cred', 'groups', 'group_id'),
        )
        print("Renamed columns to standardize naming conventions")
    except Exception as e:
        if e.args[0] == 'no such column: "desc"' or 'column "desc" does not exist' in str(e) or str(e) == '(1060, no such column: "desc")':
            print("Columns already renamed")
        elif e.args[0] == "'bool' object has no attribute 'sql'":
            print("Columns already renamed")
        else:
            print(f"Error renaming columns: {e}")


def downgrade():
    # Revert column renames
    try:
        migrate(
            migrator.rename_column('smon_agents', 'description', 'desc'),
            migrator.rename_column('smon', 'description', 'desc'),
            migrator.rename_column('smon_status_pages', 'custom_style', 'style'),
            migrator.rename_column('smon_status_pages', 'description', 'desc'),
            migrator.rename_column('telegram', 'group_id', 'groups'),
            migrator.rename_column('slack', 'group_id', 'groups'),
            migrator.rename_column('mattermost', 'group_id', 'groups'),
            migrator.rename_column('pd', 'group_id', 'groups'),
            migrator.rename_column('smon', 'enabled', 'en'),
            migrator.rename_column('servers', 'group_id', 'groups'),
            migrator.rename_column('servers', 'cred_id', 'cred'),
            migrator.rename_column('servers', 'enabled', 'enable'),
            migrator.rename_column('user', 'enabled', 'activeuser'),
            migrator.rename_column('user', 'group_id', 'groups'),
            migrator.rename_column('cred', 'key_enabled', 'enable'),
            migrator.rename_column('cred', 'group_id', 'groups'),
        )
        print("Reverted column renames")
    except Exception as e:
        print(f"Error reverting column renames: {e}")
