from peewee import *
from app.modules.db.db_model import connect, SmonGroup

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Drop check_group_id column from smon table
    try:
        migrate(
            migrator.drop_column('smon', 'check_group_id'),
        )
        print("Dropped check_group_id column from smon table")
    except Exception as e:
        print(f"Error dropping check_group_id column: {e}")


def downgrade():
    # Add check_group_id column back to smon table
    field = ForeignKeyField(SmonGroup, field=SmonGroup.id, null=True, on_delete='SET NULL')
    try:
        migrate(
            migrator.add_column('smon', 'check_group_id', field),
        )
        print("Added check_group_id column back to smon table")
    except Exception as e:
        print(f"Error adding check_group_id column: {e}")
