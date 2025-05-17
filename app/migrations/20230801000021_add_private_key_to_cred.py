from peewee import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add private_key column to cred table
    try:
        migrate(
            migrator.add_column('cred', 'private_key', TextField(null=True)),
        )
        print("Added private_key column to cred table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: private_key' or 'column "private_key" of relation "cred" already exists'
                or str(e) == '(1060, "Duplicate column name \'private_key\'")'):
            print('Column private_key already exists in cred table')
        else:
            print(f"Error adding private_key column: {e}")


def downgrade():
    # Remove private_key column from cred table
    try:
        migrate(
            migrator.drop_column('cred', 'private_key'),
        )
        print("Removed private_key column from cred table")
    except Exception as e:
        print(f"Error removing private_key column: {e}")
