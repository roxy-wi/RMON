from peewee import *
from app.modules.db.db_model import connect, Country

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add country_id column to smon table
    field = ForeignKeyField(Country, field=Country.id, null=True, on_delete='SET NULL')
    try:
        migrate(
            migrator.add_column('smon', 'country_id', field),
        )
        print("Added country_id column to smon table")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: country_id' or 'column "country_id" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'country_id\'")'):
            print('Column country_id already exists in smon table')
        else:
            print(f"Error adding country_id column: {e}")


def downgrade():
    # Remove country_id column from smon table
    try:
        migrate(
            migrator.drop_column('smon', 'country_id'),
        )
        print("Removed country_id column from smon table")
    except Exception as e:
        print(f"Error removing country_id column: {e}")
