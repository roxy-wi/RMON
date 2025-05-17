from peewee import *
from app.modules.db.db_model import connect

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add ignore_ssl_error columns to smon_smtp_check and smon_http_check tables
    try:
        migrate(
            migrator.add_column('smon_smtp_check', 'ignore_ssl_error', IntegerField(default=0)),
            migrator.add_column_default('smon_smtp_check', 'ignore_ssl_error', 0),
            migrator.add_column('smon_http_check', 'ignore_ssl_error', IntegerField(default=0)),
            migrator.add_column_default('smon_http_check', 'ignore_ssl_error', 0),
        )
        print("Added ignore_ssl_error columns to smon_smtp_check and smon_http_check tables")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: ignore_ssl_error' or 'column "ignore_ssl_error" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'ignore_ssl_error\'")'):
            print('Columns ignore_ssl_error already exist')
        else:
            print(f"Error adding ignore_ssl_error columns: {e}")


def downgrade():
    # Remove ignore_ssl_error columns from smon_smtp_check and smon_http_check tables
    try:
        migrate(
            migrator.drop_column('smon_smtp_check', 'ignore_ssl_error'),
            migrator.drop_column('smon_http_check', 'ignore_ssl_error'),
        )
        print("Removed ignore_ssl_error columns from smon_smtp_check and smon_http_check tables")
    except Exception as e:
        print(f"Error removing ignore_ssl_error columns: {e}")
