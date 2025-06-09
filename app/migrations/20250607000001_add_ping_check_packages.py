from peewee import *
from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add count_packets column to smon_ping_check table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('smon_ping_check', 'count_packets', IntegerField(default=4)),
                migrator.add_column_default('smon_ping_check', 'count_packets', 4),
            )
        else:
            migrate(
                migrator.add_column('smon_ping_check', 'count_packets', IntegerField(constraints=[SQL('DEFAULT 4')])),
                migrator.add_column_default('smon_ping_check', 'count_packets', 4),
            )
        print("Added count_packets column to smon_ping_check table")
    except Exception as e:
        print(e)
        if (e.args[0] == 'duplicate column name: count_packets' or 'column "count_packets" of relation "smon_ping_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'count_packets\'")'):
            print('Column count_packets already exists in smon_ping_check table')
        else:
            print(f"Error adding count_packets column: {e}")


def downgrade():
    # Remove count_packets column from smon_ping_check table
    try:
        migrate(
            migrator.drop_column('smon_ping_check', 'count_packets'),
        )
        print("Removed count_packets column from smon_ping_check table")
    except Exception as e:
        print(f"Error removing count_packets column: {e}")
