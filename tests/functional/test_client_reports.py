"""Reports read persisted results without a collector or aggregation runtime."""
import json
from datetime import datetime, timezone

import pytest

from test_client_management import setup
from app.modules.client_telemetry import distributions, reports, service
from app.modules.client_telemetry.models import ClientDefinition, ClientDirtyInterval, ClientRollup, ClientSegment, ClientSegmentDimension
from app.modules.client_telemetry.segments import fingerprint

pytestmark = pytest.mark.functional


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


def test_pending_recomputation_is_visible_without_losing_published_data(client, setup, published):
    ClientDirtyInterval.update(pending=True, generation=2).where(ClientDirtyInterval.id == published.id).execute()
    result = report(client, setup).get_json()
    assert result['state'] == 'processing'
    assert result['aggregation']['pending_intervals'] == 1
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
