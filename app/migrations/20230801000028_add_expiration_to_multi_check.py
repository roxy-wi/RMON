from peewee import *
from playhouse.migrate import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add expiration column to multi_check table
    try:
        migrate(
            migrator.add_column('multi_check', 'expiration', DateTimeField(null=True)),
        )
        print("Added expiration column to multi_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: expiration' or 'column "expiration" of relation "multi_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'expiration\'")'):
            print('Column expiration already exists in multi_check table')
        else:
            print(f"Error adding expiration column: {e}")


def downgrade():
    # Remove expiration column from multi_check table
    try:
        migrate(
            migrator.drop_column('multi_check', 'expiration'),
        )
        print("Removed expiration column from multi_check table")
    except Exception as e:
        print(f"Error removing expiration column: {e}")
