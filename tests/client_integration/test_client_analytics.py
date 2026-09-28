import importlib.util
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from client_runtime import server_connection
from peewee import OperationalError
from playhouse.migrate import migrate

from test_client_telemetry import collector, setup, event, send, definition
from app.modules.client_telemetry import distributions, reports, service as management
from modules.client_telemetry import aggregation, retention, segments, service
from app.modules.client_telemetry.models import (
    ClientCheck, ClientDefinition, ClientDirtyInterval, ClientObservation, ClientProject, ClientReceipt, ClientRollup, ClientSegment,
)
from app.modules.db.db_model import Groups, conn, connect, create_tables

pytestmark = pytest.mark.functional
MINUTE = aggregation.MINUTE_US


@pytest.fixture
def clock(setup, monkeypatch):
    value = [int(datetime(2026, 9, 27, 12, 0, 30, tzinfo=timezone.utc).timestamp()) * 1000000]
    monkeypatch.setattr(service, 'database_us', lambda: value[0])
    monkeypatch.setattr(management, 'database_us', lambda: value[0])
    return value


def sample(clock, minutes_ago=2, **changes):
    at = (clock[0] // MINUTE - minutes_ago) * 60
    return event(observed_at=datetime.fromtimestamp(at, timezone.utc).isoformat(), **changes)


def drain():
    for _ in range(100):
        if not aggregation.process_one():
            return
    raise AssertionError('Aggregation did not finish')


def report(client, setup, **params):
    return client.get(setup['base'] + f'/checks/{setup["check"]}/report', query_string=params, headers=setup['headers'])


def interval(setup):
    return ClientDirtyInterval.select().join(ClientDefinition).where(ClientDefinition.check == setup['check']).get()


def test_database_clock_advances_inside_transaction():
    with server_connection.conn.atomic():
        before = service.database_us()
        time.sleep(1.1)
        assert service.database_us() > before


def test_report_outcomes_metrics_and_groups(client, setup, clock):
    values = [sample(clock, duration_ms=10), sample(clock, duration_ms=20),
              sample(clock, duration_ms=999, status='error', error={'code': 'timeout'},
                     context={'environment': 'production', 'platform': 'windows'})]
    assert send(setup, values).status_code == 202
    pending = report(client, setup).get_json()
    assert pending['state'] == 'processing'
    assert pending['aggregation']['pending_intervals'] == 1
    drain()
    response = report(client, setup, group_by='platform')
    assert response.status_code == 200, response.get_json()
    value = response.get_json()
    assert value['state'] == 'ready'
    assert value['metric_label'] == 'Duration'
    assert value['aggregation']['complete'] is True
    assert value['summary']['observations'] == 3
    assert value['summary']['errors'] == 1
    assert value['summary']['error_rate'] == pytest.approx(1 / 3)
    assert value['summary']['metric']['count'] == 2
    assert value['summary']['metric']['mean'] == 15
    assert value['summary']['metric']['p95'] == pytest.approx(20, rel=.023)
    assert {row['value'] for row in value['groups']} == {'android', 'windows'}
    assert sum(row['observations'] for row in value['series']) == 3
    failure = report(client, setup, outcome='error').get_json()
    assert failure['summary']['metric']['count'] == 1
    assert failure['summary']['metric']['p95'] == 999
    assert report(client, setup, metric='items').get_json()['summary']['metric']['count'] == 3


def test_percentiles_merge_distributions_instead_of_minute_percentiles(client, setup, clock):
    values = [sample(clock, minutes_ago=3, duration_ms=10) for _ in range(100)]
    values += [sample(clock, minutes_ago=2, duration_ms=10000)]
    for offset in range(0, len(values), 50):
        assert send(setup, values[offset:offset + 50]).status_code == 202
    drain()
    value = report(client, setup, interval_minutes='5').get_json()
    assert value['summary']['metric']['count'] == 101
    assert value['summary']['metric']['p95'] == pytest.approx(10, rel=.023)
    assert value['summary']['metric']['max'] == 10000


def test_page_and_geo_grouping_include_legacy_events_and_exact_page_filters(client, setup, clock):
    lookup = Mock(); lookup.country.return_value = 'DE'
    setup['collector'].application.extensions['client_geoip'] = lookup
    page = 'https://shop.example/' + 'catalog/' * 30
    assert send(setup, [sample(clock, page_url=page + '?private=value#fragment')]).status_code == 202
    lookup.country.return_value = None
    assert send(setup, [sample(clock)]).status_code == 202
    drain()
    result = report(client, setup, group_by='_page_url').get_json()
    assert {group['value'] for group in result['groups']} == {page, None}
    assert report(client, setup, filters=json.dumps({'_page_url': page})).get_json()['summary']['observations'] == 1
    assert report(client, setup, filters=json.dumps({'_page_url': None})).get_json()['summary']['observations'] == 1
    assert {group['value'] for group in report(client, setup, group_by='country').get_json()['groups']} == {'DE', None}
    assert 'private=value' not in json.dumps(list(ClientObservation.select().dicts()))


@pytest.mark.parametrize('values', [[0], [-100, -1, 0, .01, 100], [1e-12, 1e-10, 1e-9],
                                  [-(2 ** 53 - 1), 2 ** 53 - 1], [10] * 95 + [10000] * 5])
def test_histogram_quantiles_and_merging_cover_negative_zero_and_extreme_values(values):
    direct, left, right = distributions.empty_metric(), distributions.empty_metric(), distributions.empty_metric()
    for index, value in enumerate(values):
        distributions.add_value(direct, value)
        distributions.add_value(left if index % 2 else right, value)
    distributions.merge_metric(left, right)
    assert left == direct
    result = distributions.describe(direct)
    assert result['sum'] == pytest.approx(sum(values))
    for fraction, name in [(.50, 'p50'), (.95, 'p95'), (.99, 'p99')]:
        import math
        expected = sorted(values)[math.ceil(len(values) * fraction) - 1]
        assert result[name] == pytest.approx(expected, rel=.023, abs=2 ** -30)


def test_late_arrival_during_recomputation_cannot_publish_stale_result(client, setup, clock):
    assert send(setup, [sample(clock, duration_ms=10)]).status_code == 202
    drain()
    assert send(setup, [sample(clock, duration_ms=20)]).status_code == 202
    job = aggregation.claim()
    data, received = aggregation.compute(job)
    assert send(setup, [sample(clock, duration_ms=30)]).status_code == 202
    assert aggregation.publish(job, data, received) is False
    aggregation.release(job)
    stale = report(client, setup).get_json()
    assert stale['summary']['observations'] == 1
    assert not stale['aggregation']['complete']
    drain()
    updated = report(client, setup).get_json()
    assert updated['summary']['observations'] == 3
    assert updated['summary']['metric']['sum'] == 60
    assert updated['aggregation']['complete']


def test_expired_worker_cannot_overwrite_replacement(setup, clock):
    assert send(setup, [sample(clock)]).status_code == 202
    old = aggregation.claim()
    data, received = aggregation.compute(old)
    ClientDirtyInterval.update(lease_until_us=clock[0] - 1).where(ClientDirtyInterval.id == old.id).execute()
    assert not aggregation.renew(old)
    replacement = aggregation.claim()
    assert replacement.owner != old.owner
    assert not aggregation.publish(old, data, received)
    assert not aggregation.release(old)
    data, received = aggregation.compute(replacement)
    assert aggregation.publish(replacement, data, received)
    assert interval(setup).processed_generation == interval(setup).generation


def test_concurrent_workers_claim_an_interval_only_once(setup, clock):
    assert send(setup, [sample(clock)]).status_code == 202
    def claim(_):
        try:
            return aggregation.claim()
        finally:
            server_connection.conn.close()
    conn.close()
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = list(pool.map(claim, range(6)))
    assert len([job for job in jobs if job is not None]) == 1


def test_publication_failure_rolls_back_and_retry_recovers(client, setup, clock, monkeypatch):
    assert send(setup, [sample(clock)]).status_code == 202
    with monkeypatch.context() as patch:
        patch.setattr(aggregation.ClientRollup, 'create', Mock(side_effect=OperationalError('sensitive content')))
        with pytest.raises(OperationalError):
            aggregation.process_one()
    row = interval(setup)
    assert row.processed_generation == 0
    assert row.owner is None and row.available_us > clock[0]
    assert row.last_error == 'OperationalError'
    assert not ClientRollup.select().join(ClientSegment).where(ClientSegment.definition == row.definition_id).exists()
    assert report(client, setup).get_json()['aggregation']['failed_intervals'] == 1
    assert not aggregation.process_one()
    ClientDirtyInterval.update(available_us=0).where(ClientDirtyInterval.id == row.id).execute()
    drain()
    assert report(client, setup).get_json()['summary']['observations'] == 1
    assert interval(setup).last_error is None


def test_current_minute_waits_until_closed(setup, clock):
    assert send(setup, [sample(clock, minutes_ago=0)]).status_code == 202
    assert not aggregation.process_one()
    clock[0] += MINUTE
    assert aggregation.process_one()


def test_case_sensitive_and_missing_context_filters(client, setup, clock):
    for context in [{'environment': 'production', 'platform': 'Android'},
                    {'environment': 'production', 'platform': 'android'}, {'environment': 'production'}]:
        assert send(setup, [sample(clock, context=context)]).status_code == 202
    drain()
    values = report(client, setup, group_by='platform').get_json()
    assert {item['value'] for item in values['groups']} == {'Android', 'android', None}
    for platform in ('Android', 'android', None):
        result = report(client, setup, filters=json.dumps({'platform': platform})).get_json()
        assert result['summary']['observations'] == 1


def test_custom_boolean_filters_across_definition_versions(client, setup, clock):
    assert send(setup, [sample(clock)]).status_code == 202
    changed = definition()
    changed['context']['cached'] = {'label': 'Cached', 'type': 'boolean', 'filterable': True}
    url = setup['base'] + f'/checks/{setup["check"]}/definitions'
    assert client.post(url, json=changed, headers=setup['headers']).status_code == 201
    for cached in (True, False):
        assert send(setup, [sample(clock, definition_version=2, context={'environment': 'production', 'cached': cached})]).status_code == 202
    drain()
    for cached in (True, False, None):
        response = report(client, setup, filters=json.dumps({'cached': cached}))
        assert response.status_code == 200, response.get_json()
        assert response.get_json()['summary']['observations'] == 1
    assert report(client, setup, filters=json.dumps({'cached': 'false'})).status_code == 422


def test_unknown_diagnostic_fields_are_not_report_filters(client, setup, clock):
    assert report(client, setup, filters=json.dumps({'event_id': 'anything'})).status_code == 422
    assert report(client, setup, group_by='event_id').status_code == 422
    assert report(client, setup, metric='unregistered').status_code == 422


def test_sampling_is_reported_without_population_estimates(client, setup, clock):
    assert send(setup, [sample(clock, sampling_probability=.1), sample(clock, sampling_probability=1)]).status_code == 202
    drain()
    summary = report(client, setup).get_json()['summary']
    assert summary['observations'] == 2
    assert summary['sampling'] == {'min_probability': .1, 'max_probability': 1, 'population_estimated': False}


def test_empty_report_has_no_fake_outage_or_zero_measurement(client, setup, clock):
    response = report(client, setup)
    assert response.status_code == 200
    result = response.get_json()
    assert result['state'] == 'no_data'
    assert result['summary']['metric']['count'] == 0
    assert result['summary']['metric']['p95'] is None
    assert result['summary']['error_rate'] is None


def test_reports_without_outcomes_and_optional_metrics(client, setup, clock):
    body = {'code': 'temperature', 'name': 'Temperature', 'definition': {
        'has_outcome': False, 'metrics': {'temperature': {'unit': 'C', 'label': 'Temperature'}}, 'primary_metric': 'temperature'}}
    response = client.post(setup['base'] + '/checks', json=body, headers=setup['headers'])
    assert response.status_code == 201
    setup['check'] = response.get_json()['id']
    setup['key'] = client.post(setup['base'] + '/keys', headers=setup['headers'],
                               json=dict(setup['key_body'], checks=['temperature'])).get_json()
    values = []
    for metrics in ({'temperature': -12}, {}):
        value = sample(clock, check='temperature', metrics=metrics, context={'environment': 'production'})
        value.pop('status')
        value.pop('duration_ms')
        values.append(value)
    assert send(setup, values).status_code == 202
    drain()
    result = report(client, setup).get_json()
    assert result['summary']['observations'] == 2
    assert result['summary']['metric']['count'] == 1
    assert result['summary']['metric']['mean'] == -12
    assert result['summary']['error_rate'] is None
    assert report(client, setup, outcome='ok').status_code == 422


def test_project_overview_keeps_checks_separate(client, setup, clock):
    assert send(setup, [sample(clock)]).status_code == 202
    drain()
    result = client.get(setup['base'] + '/overview', headers=setup['headers'])
    assert result.status_code == 200, result.get_json()
    assert len(result.get_json()['items']) == 1
    assert result.get_json()['items'][0]['report']['summary']['observations'] == 1


def test_reports_enforce_tenant_check_scope_and_allow_viewers(client, setup, clock, auth_headers):
    group = Groups.create(group_id=70002, name='client-reports-' + uuid4().hex)
    other = ClientProject.create(group=group.group_id, name='Foreign', created_us=0)
    foreign_check = ClientCheck.create(project=other.id, code='foreign', name='Foreign')
    prefix = setup['base'].rsplit('/', 1)[0]
    try:
        for suffix in ('/overview', f'/checks/{foreign_check.id}/report'):
            assert client.get(f'{prefix}/{other.id}{suffix}', headers=setup['headers']).status_code == 404
        assert client.get(setup['base'] + f'/checks/{foreign_check.id}/report', headers=setup['headers']).status_code == 404
        for suffix in ('/overview', f'/checks/{setup["check"]}/report'):
            response = client.get(setup['base'] + suffix, headers=auth_headers(3, 1))
            assert response.status_code == 200
            assert response.headers['Cache-Control'] == 'no-store'
            public = {'Authorization': 'Bearer ' + setup['key']['project_key']}
            assert client.get(setup['base'] + suffix, headers=public).status_code in (401, 422)
    finally:
        other.delete_instance()
        group.delete_instance()


@pytest.mark.parametrize('args', [{'interval_minutes': '2'}, {'from': '2026-09-27T10:00:01Z'},
                                 {'from': '2026-09-27T13:00:00Z'}, {'from': '2025-09-27T12:00:00Z'},
                                 {'to': '2026-09-27T13:00:00Z'}, {'filters': '[]'}, {'limit': '51'}])
def test_invalid_report_ranges_and_shapes(client, setup, clock, args):
    assert report(client, setup, **args).status_code == 422


def test_report_row_budget_never_returns_silent_partial_totals(client, setup, clock, monkeypatch):
    assert send(setup, [sample(clock, context={'environment': 'production', 'platform': str(i)}) for i in range(3)]).status_code == 202
    drain()
    monkeypatch.setattr(reports, 'MAX_ROWS', 2)
    result = report(client, setup)
    assert result.status_code == 422
    assert result.get_json()['error'] == 'report_too_large'
    assert 'summary' not in result.get_json()


def test_group_limit_marks_omitted_observations(client, setup, clock):
    assert send(setup, [sample(clock, context={'environment': 'production', 'platform': str(i)}) for i in range(3)]).status_code == 202
    drain()
    result = report(client, setup, group_by='platform', limit='1').get_json()
    assert result['summary']['observations'] == 3
    assert len(result['groups']) == 1
    assert result['groups_truncated'] and result['omitted_group_observations'] == 2


def test_segment_quota_rolls_back_complete_batch(setup, clock, monkeypatch):
    monkeypatch.setattr(segments, 'MAX_SEGMENTS_PER_MINUTE', 2)
    assert send(setup, [sample(clock, context={'environment': 'production', 'platform': 'a'})]).status_code == 202
    result = send(setup, [sample(clock, context={'environment': 'production', 'platform': platform}) for platform in ('b', 'c')])
    assert result.status_code == 429
    assert ClientObservation.select().where(ClientObservation.project == setup['project']).count() == 1


def test_retention_keeps_aggregates_after_raw_history_expires(client, setup, clock):
    assert send(setup, [sample(clock)]).status_code == 202
    minute = interval(setup).minute
    drain()
    clock[0] += 8 * 86400000000
    cleaned = retention.cleanup()
    assert cleaned['observations'] == 1 and cleaned['receipts'] == 1
    assert interval(setup).raw_deleted
    response = report(client, setup, **{'from': reports.iso_minute(minute), 'to': reports.iso_minute(minute + 1)})
    assert response.status_code == 200
    assert response.get_json()['summary']['observations'] == 1
    assert response.get_json()['aggregation']['complete']
    clock[0] += 83 * 86400000000
    assert retention.cleanup()['intervals'] == 1
    assert not ClientSegment.select().join(ClientDefinition).where(ClientDefinition.check == setup['check']).exists()


def test_retention_never_discards_unprocessed_or_leased_observations(setup, clock):
    assert send(setup, [sample(clock)]).status_code == 202
    job = aggregation.claim()
    clock[0] += 8 * 86400000000
    assert retention.cleanup()['observations'] == 0
    assert ClientObservation.select().where(ClientObservation.project == setup['project']).count() == 1
    aggregation.release(job)
    drain()
    assert retention.cleanup()['observations'] == 1


def test_cleanup_resumes_bounded_deletion_of_one_interval(setup, clock):
    assert send(setup, [sample(clock) for _ in range(3)]).status_code == 202
    drain()
    clock[0] += 8 * 86400000000
    assert retention.cleanup(batch_size=1, max_batches=1)['observations'] == 1
    assert not interval(setup).raw_deleted
    assert retention.cleanup(batch_size=1, max_batches=2)['observations'] == 2
    assert interval(setup).raw_deleted


def test_expired_receipt_still_conflicts_with_retained_observation(setup, clock):
    value = sample(clock)
    assert send(setup, [value]).status_code == 202
    drain()
    clock[0] += 3 * 86400000000
    assert retention.cleanup()['receipts'] == 1
    assert send(setup, [sample(clock, event_id=value['event_id'])]).status_code == 409


def test_existing_raw_events_without_segments_are_backfilled_by_worker(client, setup, clock):
    assert send(setup, [sample(clock)]).status_code == 202
    ClientSegment.delete().where(ClientSegment.definition == interval(setup).definition_id).execute()
    drain()
    assert report(client, setup).get_json()['summary']['observations'] == 1


def test_analytics_migration_upgrades_existing_dirty_intervals(client, setup, clock):
    assert send(setup, [sample(clock)]).status_code == 202
    row_id = interval(setup).id
    fields = ['processed_generation', 'pending', 'owner', 'lease_until_us', 'available_us', 'attempts',
              'last_error', 'last_received_us', 'updated_us', 'raw_deleted']
    migrator = connect(get_migrator=True)
    path = Path(__file__).parents[2] / 'app/migrations/20260927010000_add_client_analytics.py'
    spec = importlib.util.spec_from_file_location('client_analytics_upgrade', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        for index in conn.get_indexes('client_dirty_intervals'):
            if set(index.columns) & set(fields):
                migrate(migrator.drop_index('client_dirty_intervals', index.name))
        for name in fields:
            migrate(migrator.drop_column('client_dirty_intervals', name))
        # Startup and a retried earlier migration must not create indexes over
        # columns that the next migration has not added yet.
        create_tables()
        initial_path = Path(__file__).parents[2] / 'app/migrations/20260927000000_add_client_telemetry.py'
        initial_spec = importlib.util.spec_from_file_location('client_telemetry_before_upgrade', initial_path)
        initial = importlib.util.module_from_spec(initial_spec)
        initial_spec.loader.exec_module(initial)
        initial.upgrade()
    finally:
        migration.upgrade()
    migration.upgrade()
    row = ClientDirtyInterval.get_by_id(row_id)
    assert row.generation == 1 and row.processed_generation == 0 and row.pending and not row.raw_deleted
    drain()
    assert not interval(setup).pending
    assert report(client, setup).get_json()['summary']['observations'] == 1


def test_worker_step_runs_cleanup_and_updates_health(setup, clock, tmp_path, monkeypatch):
    from modules.client_telemetry import health as runtime_health
    from modules.client_telemetry.worker import Worker
    monkeypatch.setenv('RMON_PROCESS_HEALTH_DIR', str(tmp_path))
    assert send(setup, [sample(clock)]).status_code == 202
    worker = Worker()
    assert worker.step()
    assert runtime_health.healthy('client-analytics')
    assert not worker.step()
