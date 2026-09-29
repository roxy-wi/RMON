from datetime import datetime, timedelta

import pytest

from app.modules.db.db_model import Groups, MultiCheck, SMON, SmonGroup, SmonHistory, SmonTcpCheck
from app.modules.tools.dashboard import snapshot


NOW = datetime(2026, 9, 28, 12)


@pytest.fixture
def checks():
    group = Groups.create(name='dashboard-test', description='')
    category = SmonGroup.create(name='Core', group_id=group.group_id)
    created = []

    def make(name='API', *, status=1, enabled=1, age=20, interval=60, response=.1234, multi=None, history_status=None):
        multi = multi or MultiCheck.create(name=name, group_id=group, entity_type='agent', check_group_id=category)
        check = SMON.create(multi_check_id=multi, group_id=group.group_id, check_type='tcp', status=status,
                            enabled=enabled, response_time=str(response), check_timeout=2, retries=1)
        SmonTcpCheck.create(smon_id=check, ip='192.0.2.1', port=443, interval=interval)
        if age is not None:
            SmonHistory.create(smon_id=check, check_id=1, status=status if history_status is None else history_status,
                               response_time=response, date=NOW - timedelta(seconds=age), mes='test')
        created.append(check.id)
        return multi, check

    yield group.group_id, make
    SmonHistory.delete().where(SmonHistory.smon_id.in_(created)).execute()
    SmonTcpCheck.delete().where(SmonTcpCheck.smon_id.in_(created)).execute()
    SMON.delete().where(SMON.group_id == group.group_id).execute()
    MultiCheck.delete().where(MultiCheck.group_id == group.group_id).execute()
    category.delete_instance()
    group.delete_instance()


def test_all_locations_affect_status_and_uptime(checks):
    group, make = checks
    multi, _ = make()
    make(multi=multi, status=0)
    result = snapshot(group, now=NOW)
    card, = result['items']
    assert card['state'] == 'down'
    assert card['total_locations'] == 2 and card['locations']['up'] == 1
    assert card['response_ms'] == pytest.approx(123.4)
    assert card['uptime'] == 50
    assert card['history'][-1] == {'state': 'down', 'total': 2, 'up': 1}
    assert all(bin['state'] == 'stale' for bin in card['history'][:-1])
    assert result['counts']['down'] == 1


def test_stale_or_missing_results_are_not_reported_as_up(checks):
    group, make = checks
    make(name='old', age=181)
    make(name='new', age=None)
    make(name='slow', age=181, interval=120)
    make(name='disabled', enabled=0, age=None)
    cards = {card['name']: card for card in snapshot(group, now=NOW)['items']}
    assert cards['old']['state'] == cards['new']['state'] == 'stale'
    assert cards['old']['response_ms'] is None
    assert cards['new']['uptime'] is None
    assert cards['slow']['state'] == 'up'
    assert cards['disabled']['state'] == 'disabled'


@pytest.mark.parametrize('status,state', [(0,'down'), (2,'down'), (3,'stale'), (5,'warning'), (6,'warning'), (7,'down'), (8,'down'), (9,'warning')])
def test_current_status_classification(checks, status, state):
    group, make = checks
    make(status=status)
    assert snapshot(group, now=NOW)['items'][0]['state'] == state


def test_24_hour_window_and_group_isolation(checks):
    group, make = checks
    _, check = make()
    SmonHistory.create(smon_id=check, check_id=1, status=0, response_time=0, date=NOW-timedelta(hours=25), mes='old')
    result = snapshot(group, now=NOW)
    assert result['items'][0]['uptime'] == 100
    assert snapshot(group + 100000, now=NOW)['items'] == []
    assert snapshot(group, include_history=False, now=NOW)['items'][0]['history'] is None


def test_empty_groups_remain_manageable(checks):
    group, _ = checks
    result = snapshot(group, now=NOW)
    assert result['items'] == []
    assert result['groups'][0]['name'] == 'Core'
    assert snapshot(group + 100000, now=NOW)['groups'] == []


def test_dashboard_endpoint_requires_membership_and_uses_active_group(client, auth_headers, checks):
    group, make = checks
    make(name='not visible in Default')
    response = client.get('/rmon/dashboard/data', headers=auth_headers(1, 1))
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert all(card['name'] != 'not visible in Default' for card in response.json['items'])
    assert client.get('/rmon/dashboard/data', headers=auth_headers(3, group)).status_code in (302, 403)
    assert client.get('/rmon/dashboard/data').status_code in (302, 401)


def test_dashboard_history_obeys_subscription_policy(client, auth_headers, monkeypatch):
    monkeypatch.setattr('app.routes.smon.routes.is_feature_available', lambda feature: False)
    response = client.get('/rmon/dashboard/data', headers=auth_headers(1, 1))
    assert response.status_code == 200 and not response.json['history_available']
