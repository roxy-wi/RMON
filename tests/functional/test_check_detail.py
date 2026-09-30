from datetime import datetime, timedelta

import pytest
import requests

from app.modules.db.db_model import (MultiCheck, SMON, SmonHistory, SmonHttpCheck,
                                     SmonPingCheck, SmonTcpCheck)
from app.modules.tools import check_detail as detail


NOW = datetime(2026, 9, 29, 12)


@pytest.fixture
def detail_checks(monkeypatch):
    created, multis = [], []
    monkeypatch.setattr(detail.sql, 'get_setting', lambda name: False if name == 'use_victoria_metrics' else 'rmon')

    def make(kind='http', *, multi=None, group=1, status=1, enabled=1, response=.174, age=20, **metrics):
        if multi is None:
            multi = MultiCheck.create(name='Store <script>', description='Production', entity_type='agent', group_id=group)
            multis.append(multi.id)
        check = SMON.create(multi_check_id=multi, group_id=group, check_type=kind,
                            status=status, enabled=enabled, response_time=str(response), check_timeout=2, retries=1)
        created.append(check.id)
        if kind == 'http':
            SmonHttpCheck.create(smon_id=check, url='https://example.org', interval=60,
                                auth={'basic': {'username': 'private-user', 'password': 'private-password'}},
                                header_req={'Authorization': 'private-token'}, accepted_status_codes=[200, 204])
        elif kind == 'ping':
            SmonPingCheck.create(smon_id=check, ip='192.0.2.1', interval=60)
        else:
            SmonTcpCheck.create(smon_id=check, ip='192.0.2.1', port=443, interval=60)
        if age is not None:
            SmonHistory.create(smon_id=check, check_id=detail.CHECK_TYPES[kind], status=status,
                               date=NOW-timedelta(seconds=age), response_time=response, mes='', **metrics)
        return multi, check

    yield make
    SmonHistory.delete().where(SmonHistory.smon_id.in_(created)).execute()
    for model in (SmonHttpCheck, SmonPingCheck, SmonTcpCheck):
        model.delete().where(model.smon_id.in_(created)).execute()
    SMON.delete().where(SMON.id.in_(created)).execute()
    MultiCheck.delete().where(MultiCheck.id.in_(multis)).execute()


def test_overview_covers_all_locations_and_24_hour_summary(detail_checks):
    multi, first = detail_checks(response=.1)
    _, second = detail_checks(multi=multi, response=.3)
    SmonHistory.create(smon_id=first, check_id=2, status=2, response_time=0,
                       date=NOW-timedelta(hours=2), mes='timeout')
    SmonHistory.create(smon_id=first, check_id=2, status=1, response_time=90,
                       date=NOW-timedelta(hours=25), mes='old')
    data = detail.snapshot(multi.id, 2, 1, now=NOW)
    assert data['summary']['response_ms'] == pytest.approx(200)
    assert data['summary']['mean_ms'] == pytest.approx(200)
    assert data['summary']['uptime'] == pytest.approx(200/3)
    assert data['summary']['total_locations'] == 2
    assert {series['location_id'] for series in data['series']} == {first.id, second.id}
    assert all(series['id'] == 'response_time' and len(series['points']) == 1 for series in data['series'])
    assert data['events'][0]['date'].endswith('+00:00')
    assert not any(secret in str(data) for secret in ('private-user', 'private-password', 'private-token'))


def test_http_diagnostic_preserves_all_timings_zero_and_missing_values(detail_checks):
    multi, check = detail_checks(name_lookup='.0124', connect='.0292', app_connect='.0318',
                                 start_transfer='.0902', download='.0104', redirect='0')
    data = detail.snapshot(multi.id, 2, 1, location_id=check.id, now=NOW)
    metrics = {series['id']: series['points'][0]['y'] for series in data['series']}
    assert set(metrics) == set(detail.TIMINGS)
    assert metrics['response_time'] == 174
    assert metrics['name_lookup'] == pytest.approx(12.4)
    assert metrics['start_transfer'] == pytest.approx(90.2)
    assert metrics['redirect'] == 0
    assert metrics['pre_transfer'] is None
    assert data['selected_location'] == check.id


def test_ping_diagnostic_uses_milliseconds_and_percent(detail_checks):
    multi, check = detail_checks('ping', name_lookup='.01', connect='.02', app_connect='.005', pre_transfer='25')
    metrics = {row['id']: row for row in detail.snapshot(multi.id, 4, 1, location_id=check.id, now=NOW)['series']}
    assert metrics['avg_resp_time']['points'][0]['y'] == 10
    assert metrics['max_resp_time']['points'][0]['y'] == 20
    assert metrics['min_resp_time']['points'][0]['y'] == 5
    assert metrics['packet_loss_percent']['points'][0]['y'] == 25
    assert metrics['packet_loss_percent']['unit'] == '%'


def test_failures_and_missing_runs_are_gaps_not_zero_response(detail_checks):
    multi, check = detail_checks('tcp', status=2, response=0)
    SmonHistory.create(smon_id=check, check_id=1, date=NOW-timedelta(minutes=15), status=1, response_time=.12, mes='')
    data = detail.snapshot(multi.id, 1, 1, now=NOW)
    assert data['summary']['state'] == 'down'
    assert data['summary']['response_ms'] is None
    points = data['series'][0]['points']
    assert [point['y'] for point in points] == [120, None, None]
    assert data['events'][0]['status'] == 2


def test_empty_and_stale_locations_are_not_available(detail_checks):
    multi, check = detail_checks(age=None)
    data = detail.snapshot(multi.id, 2, 1, now=NOW, location_id=check.id)
    assert data['summary']['state'] == 'stale'
    assert data['summary']['response_ms'] is data['summary']['uptime'] is None
    assert all(series['points'] == [] for series in data['series'])
    assert data['events'] == []


def test_range_limit_is_explicit_and_daily_summary_remains_complete(detail_checks, monkeypatch):
    monkeypatch.setattr(detail, 'POINT_LIMIT', 3)
    multi, check = detail_checks()
    for minutes in range(1, 6):
        SmonHistory.create(smon_id=check, check_id=2, date=NOW-timedelta(minutes=minutes), status=1, response_time=.1, mes='')
    data = detail.snapshot(multi.id, 2, 1, now=NOW)
    assert data['truncated'] and data['point_limit'] == 3
    assert len(data['series'][0]['points']) == 3
    assert data['summary']['mean_ms'] == pytest.approx(674/6)
    assert len(data['events']) == 6


@pytest.mark.parametrize('query', ['hours=0', 'hours=2', 'hours=x', 'location=-1', 'location=x'])
def test_detail_endpoint_rejects_invalid_filters(client, auth_headers, detail_checks, query):
    multi, _ = detail_checks()
    assert client.get(f'/rmon/dashboard/{multi.id}/2/data?{query}', headers=auth_headers(1, 1)).status_code == 422


def test_detail_endpoint_checks_group_type_and_location(client, auth_headers, detail_checks):
    multi, check = detail_checks()
    other, foreign_location = detail_checks()
    url = f'/rmon/dashboard/{multi.id}/2/data'
    response = client.get(url, headers=auth_headers(3, 1))
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert client.get(url).status_code in (302, 401)
    assert client.get(url + f'?location={foreign_location.id}', headers=auth_headers(1, 1)).status_code == 404
    assert client.get(f'/rmon/dashboard/{multi.id}/1/data', headers=auth_headers(1, 1)).status_code == 404
    assert client.get(f'/rmon/dashboard/{multi.id}/1', headers=auth_headers(1, 1)).status_code == 404
    with pytest.raises(MultiCheck.DoesNotExist):
        detail.snapshot(multi.id, 2, 99999, now=NOW)


def test_detail_keeps_subscription_policy(client, auth_headers, detail_checks, monkeypatch):
    from app.modules.roxywi.exception import RoxywiPermissionError
    multi, _ = detail_checks()
    def deny(*args, **kwargs):
        raise RoxywiPermissionError('denied')
    monkeypatch.setattr('app.modules.subscription.access.require_feature', deny)
    for suffix in ('', '/data'):
        assert client.get(f'/rmon/dashboard/{multi.id}/2{suffix}', headers=auth_headers(1, 1)).status_code == 403


def test_detail_page_honors_group_membership_check(client, auth_headers, detail_checks, monkeypatch):
    multi, _ = detail_checks()
    monkeypatch.setattr('app.routes.smon.routes.roxywi_common.check_user_group_for_flask', lambda: False)
    response = client.get(f'/rmon/dashboard/{multi.id}/2', headers=auth_headers(1, 1))
    assert response.status_code == 403


def test_vm_uses_one_scoped_query_and_independent_timestamps(detail_checks, monkeypatch):
    multi, check = detail_checks()
    base = NOW.replace(tzinfo=detail.timezone.utc).timestamp()
    calls = []
    monkeypatch.setattr(detail.sql, 'get_setting', lambda name: {'use_victoria_metrics': True,
                        'rmon_name': 'rmon', 'victoria_metrics_select': 'https://metrics.invalid/api/v1'}[name])
    def get(url, **kwargs):
        calls.append((url, kwargs))
        class Response:
            def raise_for_status(self): pass
            def json(self):
                return {'status': 'success', 'data': {'result': [
                    {'metric': {'check_id':str(check.id),'metric':'response_time'}, 'values':[[base-60,'.2'],[base-20,'.174']]},
                    {'metric': {'check_id':str(check.id),'metric':'namelookup'}, 'values':[[base-50,'.012'],[base-20,'NaN']]},
                    {'metric': {'check_id':'999999','metric':'namelookup'}, 'values':[[base-20,'100']]}
                ]}}
        return Response()
    monkeypatch.setattr(detail.requests, 'get', get)
    data = detail.snapshot(multi.id, 2, 1, now=NOW, location_id=check.id)
    assert len(calls) == 1 and calls[0][1]['timeout'] == (3, 10)
    assert f'check_id=~"{check.id}"' in calls[0][1]['params']['query']
    metrics = {series['id']: series for series in data['series']}
    assert metrics['response_time']['points'][0]['y'] == 200
    assert metrics['name_lookup']['points'][0]['y'] == 12
    assert metrics['response_time']['points'][0]['x'] != metrics['name_lookup']['points'][0]['x']
    assert metrics['name_lookup']['points'][-1]['y'] is None


def test_vm_failure_is_explicit_and_does_not_leak_endpoint(client, auth_headers, detail_checks, monkeypatch):
    multi, _ = detail_checks()
    monkeypatch.setattr(detail.sql, 'get_setting', lambda name: True if name == 'use_victoria_metrics' else 'https://secret@private.invalid')
    def fail(*args, **kwargs):
        raise requests.Timeout('https://secret@private.invalid')
    monkeypatch.setattr(detail.requests, 'get', fail)
    response = client.get(f'/rmon/dashboard/{multi.id}/2/data', headers=auth_headers(1, 1))
    assert response.status_code == 503 and response.json == {'error':'metrics_unavailable'}


def test_vm_failures_are_gaps_even_when_exporter_records_zero(detail_checks):
    multi, check = detail_checks(status=2, response=0)
    series = [{'location_id':check.id, 'unit':'ms', 'points':[
        {'x':detail.iso(NOW-timedelta(seconds=30)), 'y':100},
        {'x':detail.iso(NOW-timedelta(seconds=10)), 'y':0}]}]
    location = detail.location_info(check, NOW)
    assert not detail.mask_failed_samples(series, [location], NOW-timedelta(hours=1), NOW)
    assert [point['y'] for point in series[0]['points']] == [100, None]


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', 'bad', '1e308', None])
def test_invalid_timings_never_become_nonfinite_json(value):
    assert detail.metric_value(value, 'ms') is None
