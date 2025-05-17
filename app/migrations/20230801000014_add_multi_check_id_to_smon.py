from peewee import *
from app.modules.db.db_model import connect, MultiCheck

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add multi_check_id column to smon table
    field = ForeignKeyField(MultiCheck, field=MultiCheck.id, null=True, on_delete='CASCADE')
    try:
        migrate(
            migrator.add_column('smon', 'multi_check_id', field),
        )
        print("Added multi_check_id column to smon table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: multi_check_id' or 'column "multi_check_id" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'multi_check_id\'")'):
            print('Column multi_check_id already exists in smon table')
        else:
            print(f"Error adding multi_check_id column: {e}")


def downgrade():
    # Remove multi_check_id column from smon table
    try:
        migrate(
            migrator.drop_column('smon', 'multi_check_id'),
        )
        print("Removed multi_check_id column from smon table")
    except Exception as e:
        print(f"Error removing multi_check_id column: {e}")
