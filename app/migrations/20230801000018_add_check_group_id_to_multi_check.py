from peewee import *
from app.modules.db.db_model import connect, SmonGroup

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add check_group_id column to multi_check table
    field = ForeignKeyField(SmonGroup, field=SmonGroup.id, null=True, on_delete='SET NULL')
    try:
        migrate(
            migrator.add_column('multi_check', 'check_group_id', field),
        )
        print("Added check_group_id column to multi_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: check_group_id' or 'column "check_group_id" of relation "multi_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'check_group_id\'")'):
            print('Column check_group_id already exists in multi_check table')
        else:
            print(f"Error adding check_group_id column: {e}")


def downgrade():
    # Remove check_group_id column from multi_check table
    try:
        migrate(
            migrator.drop_column('multi_check', 'check_group_id'),
        )
        print("Removed check_group_id column from multi_check table")
    except Exception as e:
        print(f"Error removing check_group_id column: {e}")
