from peewee import *
from app.modules.db.db_model import connect, Region

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Add region_id column to smon and smon_agents tables
    field = ForeignKeyField(Region, field=Region.id, null=True, on_delete='SET NULL')
    try:
        migrate(
            migrator.add_column('smon', 'region_id', field),
            migrator.add_column('smon_agents', 'region_id', field)
        )
        print("Added region_id column to smon and smon_agents tables")
    except Exception as e:
        if (e.args[0] == 'duplicate column name: region_id' or 'column "region_id" of relation "smon" already exists'
                or str(e) == '(1060, "Duplicate column name \'region_id\'")'):
            print('Column region_id already exists')
        else:
            print(f"Error adding region_id column: {e}")


def downgrade():
    # Remove region_id column from smon and smon_agents tables
    try:
        migrate(
            migrator.drop_column('smon', 'region_id'),
            migrator.drop_column('smon_agents', 'region_id')
        )
        print("Removed region_id column from smon and smon_agents tables")
    except Exception as e:
        print(f"Error removing region_id column: {e}")
