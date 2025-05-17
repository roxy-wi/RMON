from peewee import *
from app.modules.db.db_model import connect, SmonAgent

# Get the migrator for the current database
migrator = connect(get_migrator=True)


def upgrade():
    # Drop agent_id columns from check tables
    try:
        migrate(
            migrator.drop_column('smon_smtp_check', 'agent_id'),
            migrator.drop_column('smon_tcp_check', 'agent_id'),
            migrator.drop_column('smon_rabbit_check', 'agent_id'),
            migrator.drop_column('smon_ping_check', 'agent_id'),
            migrator.drop_column('smon_http_check', 'agent_id'),
            migrator.drop_column('smon_dns_check', 'agent_id'),
        )
        print("Dropped agent_id columns from check tables")
    except Exception as e:
        print(f"Error dropping agent_id columns: {e}")


def downgrade():
    # Add agent_id columns back to check tables
    field = ForeignKeyField(SmonAgent, field=SmonAgent.id, null=True, on_delete='RESTRICT')
    try:
        migrate(
            migrator.add_column('smon_smtp_check', 'agent_id', field),
            migrator.add_column('smon_tcp_check', 'agent_id', field),
            migrator.add_column('smon_rabbit_check', 'agent_id', field),
            migrator.add_column('smon_ping_check', 'agent_id', field),
            migrator.add_column('smon_http_check', 'agent_id', field),
            migrator.add_column('smon_dns_check', 'agent_id', field),
        )
        print("Added agent_id columns back to check tables")
    except Exception as e:
        print(f"Error adding agent_id columns: {e}")
