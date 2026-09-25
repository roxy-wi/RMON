import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest
from peewee import IntegrityError, SqliteDatabase

from app.modules.db.db_model import RoxyTool, Setting


@pytest.fixture
def legacy_notifications(tmp_path, monkeypatch):
    path = Path(__file__).parents[2] / 'app/migrations/20260913000000_remove_web_notifications.py'
    spec = importlib.util.spec_from_file_location('remove_web_notifications', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    database = SqliteDatabase(tmp_path / 'legacy.db')
    monkeypatch.setattr(migration, 'connect', lambda: database)
    with database.bind_ctx([Setting, RoxyTool]):
        database.create_tables([Setting, RoxyTool])
        for group_id in (1, 2):
            for param in ('enabled', 'host', 'port', 'vhost', 'queue', 'user', 'password'):
                Setting.create(param='rabbitmq_' + param, value='legacy-value', section='rabbitmq', desc='', group_id=group_id)
            Setting.create(param='mail_smtp_host', value='mail.example.test', section='mail', desc='', group_id=group_id)
        for service in ('rmon-socket', 'rabbitmq-server', 'rmon-server', 'fail2ban'):
            RoxyTool.create(name=service, current_version='1.0', new_version='1.1', is_roxy=1, desc='')
        try:
            yield database, migration
        finally:
            database.close()


def test_migration_removes_only_retired_settings_and_services_and_is_repeatable(legacy_notifications):
    database, migration = legacy_notifications
    migration.upgrade()
    migration.upgrade()
    assert list(Setting.select(Setting.param, Setting.value, Setting.group_id).order_by(Setting.group_id).tuples()) == [
        ('mail_smtp_host', 'mail.example.test', 1), ('mail_smtp_host', 'mail.example.test', 2)]
    assert {row.name for row in RoxyTool.select()} == {'rmon-server', 'fail2ban'}
    with pytest.raises(RuntimeError, match='database backup'):
        migration.downgrade()


def test_migration_rolls_back_settings_if_service_cleanup_fails(legacy_notifications):
    database, migration = legacy_notifications
    database.execute_sql("CREATE TRIGGER reject_cleanup BEFORE DELETE ON roxy_tools BEGIN SELECT RAISE(ABORT, 'blocked'); END")
    with pytest.raises(IntegrityError, match='blocked'):
        migration.upgrade()
    assert Setting.select().where(Setting.section == 'rabbitmq').count() == 14
    assert RoxyTool.select().count() == 4


def test_retired_services_are_not_exposed_or_controllable_even_before_migration(legacy_notifications, monkeypatch):
    from app.modules.db import roxy as service_sql
    from app.modules.roxywi import roxy
    from app.modules.tools import common
    assert set(service_sql.get_all_tools()) == {'rmon-server', 'fail2ban'}
    assert set(service_sql.get_roxy_tools()) == {'rmon-server', 'fail2ban'}
    monkeypatch.delenv('RMON_CONTAINER', raising=False)
    monkeypatch.setattr(roxy.os, 'system', Mock(side_effect=AssertionError('Retired service was controlled')))
    monkeypatch.setattr(common.server_mod, 'subprocess_execute', Mock(side_effect=AssertionError('Retired package was installed')))
    for name in ('rmon-socket', 'rabbitmq-server'):
        assert roxy.action_service('restart', name) == 'error: Unsupported service'
        with pytest.raises(Exception, match='not part of RMON'):
            common.update_roxy_wi(name)


@pytest.mark.functional
def test_settings_api_and_channel_page_no_longer_offer_web_notifications(client, auth_headers):
    headers = auth_headers(1, 1)
    response = client.get('/api/v1.0/settings', headers=headers)
    assert response.status_code == 200
    assert not any(row['section'] == 'rabbitmq' for row in response.json)
    assert client.get('/api/v1.0/settings/rabbitmq', headers=headers).status_code == 404
    html = client.get('/channel/load', headers=headers)
    assert html.status_code == 200
    assert "sendCheckMessage('web')" not in html.get_data(as_text=True)
    assert "sendCheckMessage('email')" in html.get_data(as_text=True)


@pytest.mark.functional
def test_email_test_remains_available_and_retired_sender_is_rejected(client, auth_headers, monkeypatch):
    from app.modules.tools import alerting
    send_email = Mock(return_value='ok')
    monkeypatch.setattr(alerting, 'check_email_alert', send_email)
    headers = auth_headers(1, 1)
    rejected = client.post('/channel/check', headers=headers, json={'sender': 'web'})
    assert rejected.status_code == 400
    send_email.assert_not_called()
    accepted = client.post('/channel/check', headers=headers, json={'sender': 'email'})
    assert accepted.status_code == 200
    assert accepted.json == {'status': 'success'}
    send_email.assert_called_once_with()


@pytest.mark.functional
@pytest.mark.parametrize('payload', [{}, [], {'sender': []}, {'sender': {}}])
def test_invalid_notification_test_sender_is_rejected(client, auth_headers, payload):
    response = client.post('/channel/check', headers=auth_headers(1, 1), json=payload)
    assert response.status_code == 400
    assert response.json == {'error': 'Unsupported notification channel'}
