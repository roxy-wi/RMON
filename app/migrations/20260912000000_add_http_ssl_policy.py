from peewee import CharField, SQL
from playhouse.migrate import migrate

from app.modules.db.db_model import connect


def upgrade():
    database = connect()
    if 'ssl_policy' not in {column.name for column in database.get_columns('smon_http_check')}:
        migrate(connect(get_migrator=True).add_column(
            'smon_http_check', 'ssl_policy',
            CharField(default='default', constraints=[SQL("DEFAULT 'default'")]),
        ))


def downgrade():
    database = connect()
    if 'ssl_policy' in {column.name for column in database.get_columns('smon_http_check')}:
        migrate(connect(get_migrator=True).drop_column('smon_http_check', 'ssl_policy'))
