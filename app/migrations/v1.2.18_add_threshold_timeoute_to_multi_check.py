from peewee import *
from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add threshold_timeout column to multi_check table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('multi_check', 'threshold_timeout', FloatField(default=0)),
                migrator.add_column_default('multi_check', 'threshold_timeout', 0),
            )
        else:
            migrate(
                migrator.add_column('multi_check', 'threshold_timeout', FloatField(constraints=[SQL("DEFAULT 0")])),
                migrator.add_column_default('multi_check', 'threshold_timeout', 0),
            )
        print("Added threshold_timeout column to multi_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: threshold_timeout' or 'column "threshold_timeout" of relation "multi_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'threshold_timeout\'")'):
            print('Column threshold_timeout already exists in multi_check table')
        else:
            print(f"Error adding threshold_timeout column: {e}")


def downgrade():
    # Remove threshold_timeout column from multi_check table
    try:
        migrate(
            migrator.drop_column('multi_check', 'threshold_timeout'),
        )
        print("Removed threshold_timeout column from multi_check table")
    except Exception as e:
        print(f"Error removing threshold_timeout column: {e}")
