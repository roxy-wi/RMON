from app.modules.db.db_model import connect, Version

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Insert version record with version '1.0'
    try:
        Version.insert(version='1.0').execute()
        print("Inserted version record with version '1.0'")
    except Exception as e:
        print(f"Error inserting version record: {e}")


def downgrade():
    # Remove version record with version '1.0'
    try:
        Version.delete().where(Version.version == '1.0').execute()
        print("Removed version record with version '1.0'")
    except Exception as e:
        print(f"Error removing version record: {e}")
