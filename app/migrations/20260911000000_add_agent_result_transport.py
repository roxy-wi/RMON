from peewee import CharField, DateTimeField
from playhouse.migrate import migrate

from app.modules.db.db_model import Groups, Setting, connect
from app.modules.common.agent_transport import setting_rows, DEFAULTS


FIELDS = {
    'result_transport': CharField(null=True),
    'applied_result_transport': CharField(null=True),
    'transport_settings_hash': CharField(null=True),
    'transport_checked_at': DateTimeField(null=True),
}


def upgrade():
    database = connect()
    migrator = connect(get_migrator=True)
    existing = {column.name for column in database.get_columns('smon_agents')}
    for name, field in FIELDS.items():
        if name not in existing:
            migrate(migrator.add_column('smon_agents', name, field))
    for group in Groups.select():
        Setting.insert_many(setting_rows(group.group_id)).on_conflict_ignore().execute()


def downgrade():
    database = connect()
    migrator = connect(get_migrator=True)
    Setting.delete().where(Setting.param.in_(tuple(DEFAULTS))).execute()
    existing = {column.name for column in database.get_columns('smon_agents')}
    for name in FIELDS:
        if name in existing:
            migrate(migrator.drop_column('smon_agents', name))
