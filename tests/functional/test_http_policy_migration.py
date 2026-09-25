import importlib.util
from pathlib import Path

from peewee import SqliteDatabase
from playhouse.migrate import SqliteMigrator


def test_http_policy_migration_preserves_checks_and_is_repeatable(tmp_path, monkeypatch):
    path = Path(__file__).parents[2] / 'app/migrations/20260912000000_add_http_ssl_policy.py'
    spec = importlib.util.spec_from_file_location('http_policy_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    database = SqliteDatabase(tmp_path / 'legacy.db')
    monkeypatch.setattr(migration, 'connect', lambda get_migrator=False:
                        SqliteMigrator(database) if get_migrator else database)
    with database:
        database.execute_sql('CREATE TABLE smon_http_check (smon_id INTEGER PRIMARY KEY, url TEXT NOT NULL)')
        database.execute_sql("INSERT INTO smon_http_check VALUES (1, 'https://example.test')")
        migration.upgrade()
        assert database.execute_sql('SELECT url, ssl_policy FROM smon_http_check').fetchone() == (
            'https://example.test', 'default')
        database.execute_sql("UPDATE smon_http_check SET ssl_policy = 'require_https' WHERE smon_id = 1")
        migration.upgrade()
        database.execute_sql("INSERT INTO smon_http_check (smon_id, url) VALUES (2, 'http://example.test')")
        assert database.execute_sql('SELECT ssl_policy FROM smon_http_check ORDER BY smon_id').fetchall() == [
            ('require_https',), ('default',)]
        migration.downgrade()
        migration.downgrade()
        assert database.execute_sql('SELECT COUNT(*) FROM smon_http_check').fetchone() == (2,)
        migration.upgrade()
        assert database.execute_sql('SELECT DISTINCT ssl_policy FROM smon_http_check').fetchall() == [('default',)]
