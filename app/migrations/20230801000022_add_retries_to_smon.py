from peewee import *
from app.modules.db.db_model import connect, mysql_enable

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add retries column to smon table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('smon', 'retries', IntegerField(default=3)),
                migrator.add_column_default('smon', 'retries', 3),
            )
        else:
            migrate(
                migrator.add_column('smon', 'retries', IntegerField(constraints=[SQL('DEFAULT 3')])),
                migrator.add_column_default('smon', 'retries', 3),
            )
        print("Added retries column to smon table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: retries' or 'column "retries" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'retries\'")'):
            print('Column retries already exists in smon table')
        else:
            print(f"Error adding retries column: {e}")


def downgrade():
    # Remove retries column from smon table
    try:
        migrate(
            migrator.drop_column('smon', 'retries'),
        )
        print("Removed retries column from smon table")
    except Exception as e:
        print(f"Error removing retries column: {e}")
