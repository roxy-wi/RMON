from peewee import *
from app.modules.db.db_model import connect, mysql_enable

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add priority column to multi_check table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('multi_check', 'priority', CharField(default='critical')),
                migrator.add_column_default('multi_check', 'priority', 'critical'),
            )
        else:
            migrate(
                migrator.add_column('multi_check', 'priority', CharField(constraints=[SQL("DEFAULT 'critical'")])),
                migrator.add_column_default('multi_check', 'priority', 'critical'),
            )
        print("Added priority column to multi_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: priority' or 'column "priority" of relation "multi_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'priority\'")'):
            print('Column priority already exists in multi_check table')
        else:
            print(f"Error adding priority column: {e}")


def downgrade():
    # Remove priority column from multi_check table
    try:
        migrate(
            migrator.drop_column('multi_check', 'priority'),
        )
        print("Removed priority column from multi_check table")
    except Exception as e:
        print(f"Error removing priority column: {e}")
