from peewee import *
from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable, Version, SMON, MultiCheck

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Step 1: Add name and description fields to MultiCheck
    name_field = CharField(null=True)
    description_field = CharField(null=True)
    
    try:
        migrate(
            migrator.add_column('multi_check', 'name', name_field),
            migrator.add_column('multi_check', 'description', description_field),
        )
        print("Added name and description columns to multi_check table")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("Column name or description already exists in multi_check table")
        else:
            print(f"Error adding columns to multi_check table: {e}")

    # Step 2: Migrate data from SMON to MultiCheck
    try:
        # Get all SMON records that have a multi_check_id
        smon_records = SMON.select()
        
        # For each SMON record, update the corresponding MultiCheck record
        for smon in smon_records:
            MultiCheck.update(
                name=smon.name,
                description=smon.description
            ).where(MultiCheck.id == smon.multi_check_id).execute()
        
        print("Migrated name and description data from SMON to MultiCheck")
    except Exception as e:
        print(f"Error migrating data from SMON to MultiCheck: {e}")

    # Step 3: Remove name and description fields from SMON
    try:
        migrate(
            migrator.drop_column('smon', 'name'),
            migrator.drop_column('smon', 'description'),
            migrator.drop_column('smon', 'body_status'),
        )
        print("Removed name and description columns from smon table")
    except Exception as e:
        print(f"Error removing columns from smon table: {e}")

    # Update version
    try:
        Version.update(version='1.2.19').execute()
        print("Updated version record to '1.2.19'")
    except Exception as e:
        print(f"Error updating version record: {e}")


def downgrade():
    # Step 1: Add name and description fields back to SMON
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('smon', 'name', CharField(null=True)),
                migrator.add_column('smon', 'description', CharField(null=True)),
            )
        else:
            migrate(
                migrator.add_column('smon', 'name', CharField(null=True)),
                migrator.add_column('smon', 'description', CharField(null=True)),
            )
        print("Added name and description columns back to smon table")
    except Exception as e:
        print(f"Error adding columns back to smon table: {e}")

    # Step 2: Migrate data back from MultiCheck to SMON
    try:
        # Get all SMON records that have a multi_check_id
        smon_records = SMON.select().where(SMON.multi_check_id.is_null(False))
        
        # For each SMON record, update it with data from the corresponding MultiCheck record
        for smon in smon_records:
            multi_check = MultiCheck.get_by_id(smon.multi_check_id)
            SMON.update(
                name=multi_check.name,
                description=multi_check.description
            ).where(SMON.id == smon.id).execute()
        
        print("Migrated name and description data back from MultiCheck to SMON")
    except Exception as e:
        print(f"Error migrating data back from MultiCheck to SMON: {e}")

    # Step 3: Remove name and description fields from MultiCheck
    try:
        migrate(
            migrator.drop_column('multi_check', 'name'),
            migrator.drop_column('multi_check', 'description'),
        )
        print("Removed name and description columns from multi_check table")
    except Exception as e:
        print(f"Error removing columns from multi_check table: {e}")

    # Update version
    try:
        Version.update(version='1.2.18').execute()
        print("Reverted version record to '1.2.18'")
    except Exception as e:
        print(f"Error reverting version record: {e}")