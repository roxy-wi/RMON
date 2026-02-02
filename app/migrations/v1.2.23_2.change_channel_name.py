from playhouse.migrate import migrate
from app.modules.db.db_model import connect, Version

migrator = connect(get_migrator=True)


def upgrade():
    try:
        # Add migrations for each table that needs the column renamed
        migrate(
            migrator.rename_column('telegram', 'chanel_name', 'channel_name'),
            migrator.rename_column('slack', 'chanel_name', 'channel_name'),
            migrator.rename_column('pd', 'chanel_name', 'channel_name'),
            migrator.rename_column('mattermost', 'chanel_name', 'channel_name'),
            migrator.rename_column('emails', 'chanel_name', 'channel_name')
        )
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

    # Update version
    try:
        Version.update(version='1.2.23.2').execute()
        print("Updated version record to '1.2.23.2'")
    except Exception as e:
        print(f"Error updating version record: {e}")

    return True


def downgrade():
    try:
        # Revert the changes if needed
        migrate(
            migrator.rename_column('telegram', 'channel_name', 'chanel_name'),
            migrator.rename_column('slack', 'channel_name', 'chanel_name'),
            migrator.rename_column('pd', 'channel_name', 'chanel_name'),
            migrator.rename_column('mattermost', 'channel_name', 'chanel_name'),
            migrator.rename_column('emails', 'channel_name', 'chanel_name')
        )
    except Exception as e:
        print(f"Error during migration rollback: {e}")
        return False

    # Update version
    try:
        Version.update(version='1.2.23.1').execute()
        print("Updated version record to '1.2.23.1'")
    except Exception as e:
        print(f"Error updating version record: {e}")

    return True
