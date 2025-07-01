from peewee import *
from playhouse.migrate import *
from app.modules.db.db_model import connect, mysql_enable

migrator = connect(get_migrator=True)


def upgrade():
    try:
        if mysql_enable:
            migrate(
                migrator.add_column('alert_event', 'alert_key', CharField(default='', max_length=255)),
                migrator.add_column('alert_state', 'alert_key', CharField(default='', max_length=255)),
                migrator.add_column_default('alert_event', 'alert_key', ''),
                migrator.add_column_default('alert_state', 'alert_key', ''),
            )
        else:
            migrate(
                migrator.add_column('alert_event', 'alert_key', CharField(constraints=[SQL("DEFAULT ''")], max_length=255)),
                migrator.add_column('alert_state', 'alert_key', CharField(constraints=[SQL("DEFAULT ''")], max_length=255)),
                migrator.add_column_default('alert_event', 'alert_key', ''),
                migrator.add_column_default('alert_state', 'alert_key', ''),
            )
        print("Added alert_key column to alert_event and alert_state tables")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("Column alert_key already exists in one of the tables")
        else:
            print(f"Error adding alert_key column: {e}")

    # Создание индексов
    try:
        migrate(
            migrator.add_index('alert_event', ('alert_key',), False),
            migrator.add_index('alert_state', ('alert_key',), False),
        )
        print("Created indexes on alert_key in alert_event and alert_state")
    except Exception as e:
        print(f"Error creating alert_key indexes: {e}")

    # Удаляем старый уникальный индекс и создаём новый составной
    try:
        if not mysql_enable:
            # PostgreSQL-only
            from app.modules.db.db_model import db
            db.execute_sql('DROP INDEX IF EXISTS alert_state_multi_check_id_key')
            db.execute_sql('CREATE UNIQUE INDEX IF NOT EXISTS alert_state_multi_check_id_alert_key_idx '
                           'ON alert_state (multi_check_id, alert_key)')
            print("Replaced unique index on alert_state with composite (multi_check_id, alert_key)")
        else:
            print("Skip composite index update on MySQL (manual intervention may be required)")
    except Exception as e:
        print(f"Error updating unique index on alert_state: {e}")


def downgrade():
    try:
        migrate(
            migrator.drop_index('alert_event', 'alert_event_alert_key'),
            migrator.drop_index('alert_state', 'alert_state_alert_key'),
        )
        print("Removed indexes on alert_key in alert_event and alert_state")
    except Exception as e:
        print(f"Error dropping indexes: {e}")

    try:
        migrate(
            migrator.drop_column('alert_event', 'alert_key'),
            migrator.drop_column('alert_state', 'alert_key'),
        )
        print("Removed alert_key column from alert_event and alert_state")
    except Exception as e:
        print(f"Error removing alert_key column: {e}")
