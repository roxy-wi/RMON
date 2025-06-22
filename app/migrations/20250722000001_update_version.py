from app.modules.db.db_model import connect, Version

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    try:
        Version.update(version='1.2.17').execute()
        print("Update version record with version '1.2.17'")
    except Exception as e:
        print(f"Error inserting version record: {e}")


def downgrade():
    try:
        Version.update(version='1.2.16').execute().execute()
        print("Removed version record with version '1.2.16'")
    except Exception as e:
        print(f"Error removing version record: {e}")
