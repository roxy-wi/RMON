from peewee import *
from app.modules.db.db_model import connect, mysql_enable

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add shared column to cred table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('cred', 'shared', IntegerField(default=0)),
            )
        else:
            migrate(
                migrator.add_column('cred', 'shared', IntegerField(constraints=[SQL('DEFAULT 0')])),
            )
        print("Added shared column to cred table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: shared' or 'column "shared" of relation "cred" already exists'
                or str(e) == '(1060, "Duplicate column name \'shared\'")'):
            print('Column shared already exists in cred table')
        else:
            print(f"Error adding shared column: {e}")


def downgrade():
    # Remove shared column from cred table
    try:
        migrate(
            migrator.drop_column('cred', 'shared'),
        )
        print("Removed shared column from cred table")
    except Exception as e:
        print(f"Error removing shared column: {e}")
