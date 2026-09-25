from app.modules.db.db_model import connect, Setting, RoxyTool


def upgrade():
    database = connect()
    with database.connection_context(), database.atomic():
        Setting.delete().where(Setting.section == 'rabbitmq').execute(database)
        RoxyTool.delete().where(RoxyTool.name.in_(('rmon-socket', 'rabbitmq-server'))).execute(database)


def downgrade():
    raise RuntimeError('Restore a database backup to recover removed web-notification settings.')
