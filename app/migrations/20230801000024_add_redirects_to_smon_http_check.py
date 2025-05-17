from peewee import *
from app.modules.db.db_model import connect, mysql_enable

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add redirects column to smon_http_check table
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('smon_http_check', 'redirects', IntegerField(default=10)),
                migrator.add_column_default('smon_http_check', 'redirects', 10),
            )
        else:
            migrate(
                migrator.add_column('smon_http_check', 'redirects', IntegerField(constraints=[SQL('DEFAULT 10')])),
                migrator.add_column_default('smon_http_check', 'redirects', 10),
            )
        print("Added redirects column to smon_http_check table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: redirects' or 'column "redirects" of relation "smon_http_check" already exists'
                or str(e) == '(1060, "Duplicate column name \'redirects\'")'):
            print('Column redirects already exists in smon_http_check table')
        else:
            print(f"Error adding redirects column: {e}")


def downgrade():
    # Remove redirects column from smon_http_check table
    try:
        migrate(
            migrator.drop_column('smon_http_check', 'redirects'),
        )
        print("Removed redirects column from smon_http_check table")
    except Exception as e:
        print(f"Error removing redirects column: {e}")
