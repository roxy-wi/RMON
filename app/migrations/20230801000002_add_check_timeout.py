from peewee import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add check_timeout column to smon table
    try:
        migrate(
            migrator.add_column('smon', 'check_timeout', IntegerField(default=2)),
            migrator.add_column_default('smon', 'check_timeout', 2),
        )
        print("Added check_timeout column to smon table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: check_timeout' or 'column "check_timeout" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'check_timeout\'")'):
            print('Column check_timeout already exists in smon table')
        else:
            print(f"Error adding check_timeout column: {e}")


def downgrade():
    # Remove check_timeout column from smon table
    try:
        migrate(
            migrator.drop_column('smon', 'check_timeout'),
        )
        print("Removed check_timeout column from smon table")
    except Exception as e:
        print(f"Error removing check_timeout column: {e}")
