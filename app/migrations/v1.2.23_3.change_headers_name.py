from playhouse.migrate import migrate
from app.modules.db.db_model import connect, Version

migrator = connect(get_migrator=True)


def upgrade():
    try:
        # Add migrations for each table that needs the column renamed
        migrate(
            migrator.rename_column('smon_http_check', 'headers', 'header_req'),
        )
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

    # Update version
    try:
        Version.update(version='1.2.23.3').execute()
        print("Updated version record to '1.2.23.3'")
    except Exception as e:
        print(f"Error updating version record: {e}")

    return True


def downgrade():
    try:
        # Revert the changes if needed
        migrate(
            migrator.rename_column('header_req', 'header_req', 'headers'),
        )
    except Exception as e:
        print(f"Error during migration rollback: {e}")
        return False

    # Update version
    try:
        Version.update(version='1.2.23.2').execute()
        print("Updated version record to '1.2.23.2'")
    except Exception as e:
        print(f"Error updating version record: {e}")

    return True
