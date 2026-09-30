"""Reports read persisted results without a collector or aggregation runtime."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock, call

import pytest
from peewee import OperationalError

from test_client_management import setup
from app.modules.client_telemetry import distributions, reports, service
from app.modules.client_telemetry.models import ClientDefinition, ClientDirtyInterval, ClientRollup, ClientSegment, ClientSegmentDimension
from app.modules.client_telemetry.segments import fingerprint
from app.modules.db.db_model import ReconnectMySQLDatabase

pytestmark = pytest.mark.functional


@pytest.fixture
def mysql_snapshot(monkeypatch):
    database = ReconnectMySQLDatabase('unused')
    driver = Mock(server_version='8.4.0')
    connect = Mock(return_value=driver)
    # Keep Peewee's real transaction and reconnect logic; replace only the driver.
    monkeypatch.setattr(database, '_connect', connect)
    monkeypatch.setattr(reports, 'conn', database)
    yield database, driver, connect
    database.close()


def test_mysql_report_snapshot_keeps_repeatable_read(mysql_snapshot):
    database, driver, connect = mysql_snapshot
    with reports.snapshot():
        assert database.in_transaction()
    assert driver.cursor.return_value.execute.call_args_list == [
        call('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'), call('BEGIN'), call('COMMIT'),
    ]
    assert not database.in_transaction()
    connect.assert_called_once_with()


@pytest.mark.parametrize('failed_statement', [0, 1], ids=['isolation', 'begin'])
def test_mysql_report_snapshot_reapplies_isolation_after_reconnect(mysql_snapshot, failed_statement):
    database, first_driver, connect = mysql_snapshot
    second_driver = Mock(server_version='8.4.0')
    connect.side_effect = [first_driver, second_driver]
    first_driver.cursor.return_value.execute.side_effect = [None] * failed_statement + [
        OperationalError(2013, 'Lost connection to MySQL server'),
    ]
    with reports.snapshot():
        assert database.in_transaction()
    first_driver.close.assert_called_once_with()
    assert connect.call_count == 2
    assert second_driver.cursor.return_value.execute.call_args_list == [
        call('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'), call('BEGIN'), call('COMMIT'),
    ]


def test_mysql_report_snapshot_does_not_retry_inside_transaction(mysql_snapshot):
    database, driver, connect = mysql_snapshot
    driver.cursor.return_value.execute.side_effect = [None, None,
        OperationalError(2013, 'Lost connection to MySQL server'), None]
    with pytest.raises(OperationalError, match='Lost connection'):
        with reports.snapshot():
            database.execute_sql('SELECT 1')
    assert driver.cursor.return_value.execute.call_args_list == [
        call('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'), call('BEGIN'),
        call('SELECT 1', ()), call('ROLLBACK'),
    ]
    connect.assert_called_once_with()
    assert not database.in_transaction()


def test_mysql_report_snapshot_propagates_other_errors(mysql_snapshot):
    database, driver, connect = mysql_snapshot
    driver.cursor.return_value.execute.side_effect = OperationalError(1231, 'Invalid isolation level')
    with pytest.raises(OperationalError, match='Invalid isolation level'):
        with reports.snapshot():
            pytest.fail('Snapshot must not start after a database error')
    connect.assert_called_once_with()
    assert not database.in_transaction()


def test_mysql_default_transaction_still_works(mysql_snapshot):
    database, driver, connect = mysql_snapshot
    with database.atomic():
        assert database.in_transaction()
    assert driver.cursor.return_value.execute.call_args_list == [call('BEGIN'), call('COMMIT')]
    connect.assert_called_once_with()


@pytest.fixture
def published(setup, monkeypatch):
    now = int(datetime(2026, 9, 27, 12, 0, 30, tzinfo=timezone.utc).timestamp()) * 1000000
    monkeypatch.setattr(service, 'database_us', lambda: now)
    definition = ClientDefinition.get(ClientDefinition.check == setup['check'])
    minute = now // 60000000 - 2
    for platform, values in [('android', [10, 20]), ('windows', [999])]:
        dimensions = {'environment': 'production', 'platform': platform}
        segment = ClientSegment.create(definition=definition.id, minute=minute,
                                       signature=fingerprint(dimensions), dimensions=dimensions)
        for name, value in dimensions.items():
            ClientSegmentDimension.create(segment=segment.id, name=name, value_hash=fingerprint(value))
        state = distributions.empty_state()
        for value in values:
            distributions.add_event(state, {'duration_ms': value, 'status': 'error' if value == 999 else 'ok',
                                            'metrics': {'items': 48}})
        ClientRollup.create(segment=segment.id, generation=1, algorithm=distributions.ALGORITHM, state=state)
    interval = ClientDirtyInterval.create(definition=definition.id, minute=minute, generation=1,
                                          processed_generation=1, pending=False, updated_us=now)
    return interval


def report(client, setup, **params):
    return client.get(setup['base'] + f'/checks/{setup["check"]}/report', query_string=params, headers=setup['headers'])


def test_report_reads_published_histograms_and_groups(client, setup, published):
    response = report(client, setup, group_by='platform')
    assert response.status_code == 200
    result = response.get_json()
    assert result['state'] == 'ready' and result['aggregation']['complete']
    assert result['summary']['observations'] == 3
    assert result['summary']['error_rate'] == pytest.approx(1 / 3)
    assert result['summary']['metric']['mean'] == 15
    assert result['summary']['metric']['p95'] == pytest.approx(20, rel=.023)
    assert {item['value'] for item in result['groups']} == {'android', 'windows'}
    assert report(client, setup, outcome='error').get_json()['summary']['metric']['mean'] == 999
    assert report(client, setup, metric='items').get_json()['summary']['metric']['count'] == 3
    assert report(client, setup, filters=json.dumps({'platform': 'android'})).get_json()['summary']['observations'] == 2


@pytest.mark.parametrize('last_error', [None, 'aggregation_failed'])
def test_pending_recomputation_is_visible_without_losing_published_data(client, setup, published, last_error):
    ClientDirtyInterval.update(pending=True, generation=2, last_error=last_error).where(ClientDirtyInterval.id == published.id).execute()
    result = report(client, setup).get_json()
    assert result['state'] == 'processing'
    assert result['aggregation']['pending_intervals'] == 1
    assert result['aggregation']['failed_intervals'] == int(last_error is not None)
    assert type(result['aggregation']['pending_intervals']) is int
    assert type(result['aggregation']['failed_intervals']) is int
    assert result['summary']['observations'] == 3


@pytest.mark.parametrize('pending,failed', [
    (None, None), (Decimal(0), Decimal(0)), (Decimal(1), Decimal(0)), (Decimal(2), Decimal(1)),
], ids=['empty', 'complete', 'pending', 'failed'])
def test_mysql_decimal_aggregation_counts_remain_json_numbers(client, setup, published, monkeypatch, pending, failed):
    # Reproduce MySQL SUM results on every backend and exercise Flask's JSON encoding.
    query = Mock()
    query.where.return_value = query
    query.dicts.return_value = query
    query.get.return_value = {'pending': pending, 'failed': failed,
                             'oldest': published.minute if pending else None,
                             'last_received': None, 'last_processed': published.updated_us}
    monkeypatch.setattr(ClientDirtyInterval, 'select', Mock(return_value=query))
    response = report(client, setup)
    assert response.status_code == 200
    result = response.get_json()
    aggregation = result['aggregation']
    for field, expected in [('pending_intervals', int(pending or 0)), ('failed_intervals', int(failed or 0))]:
        assert type(aggregation[field]) is int
        assert aggregation[field] == expected
    assert aggregation['complete'] is (not pending)
    assert result['state'] == ('processing' if pending else 'ready')
    assert result['summary']['observations'] == 3


def test_report_requires_no_collection_process(client, setup):
    result = report(client, setup).get_json()
    assert result['state'] == 'no_data'
    assert result['summary']['metric']['p95'] is None
    assert result['summary']['error_rate'] is None
    assert client.post('/api/v1/client/events', json={}).status_code in (401, 404)


@pytest.mark.parametrize('params', [{'group_by': 'event_id'}, {'metric': 'unregistered'}, {'interval_minutes': '2'},
                                  {'filters': '[]'}, {'limit': '51'}, {'from': '2026-09-27T10:00:01Z'}])
def test_report_rejects_invalid_queries(client, setup, published, params):
    assert report(client, setup, **params).status_code == 422


def test_report_budget_returns_explicit_error(client, setup, published, monkeypatch):
    monkeypatch.setattr(reports, 'MAX_ROWS', 1)
    response = report(client, setup)
    assert response.status_code == 422
    assert response.get_json()['error'] == 'report_too_large'


def test_viewer_can_read_aggregates(client, setup, published, auth_headers):
    setup['headers'] = auth_headers(3, 1)
    assert report(client, setup).status_code == 200
    assert client.get(setup['base'] + '/overview', headers=setup['headers']).get_json()['items'][0]['report']['summary']['observations'] == 3
