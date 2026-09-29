import copy
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest

from client_runtime import server_connection
from peewee import IntegrityError, MySQLDatabase, OperationalError

from modules.client_telemetry import service
from modules.client_telemetry.http import create_ingest_app
from app.modules.client_telemetry.models import (
    CLIENT_TABLES, ClientCheck, ClientDefinition, ClientDirtyInterval, ClientKey,
    ClientObservation, ClientProject, ClientReceipt,
)
from app.modules.db.db_model import ActionHistory, Groups, conn, connect

pytestmark = pytest.mark.functional
API = '/api/v1.0/client/projects'
INGEST = '/api/v1/client/events'


def definition():
    return {'has_outcome': True, 'duration': {'label': 'Duration', 'unit': 'ms', 'minimum': 0},
            'primary_metric': 'duration_ms',
            'metrics': {'items': {'label': 'Items', 'unit': 'count', 'type': 'integer', 'required': True}},
            'context': {'region': {'label': 'Region', 'type': 'enum', 'values': ['EU', 'US'], 'filterable': True}}}


def event(**updates):
    value = {'event_id': str(uuid4()), 'check': 'catalog.load', 'definition_version': 1,
             'observed_at': datetime.now(timezone.utc).isoformat(), 'status': 'ok', 'duration_ms': 243,
             'metrics': {'items': 48}, 'context': {'platform': 'android', 'environment': 'production', 'region': 'EU'}}
    value.update(updates)
    return value


@pytest.fixture
def collector():
    application = create_ingest_app()
    application.config['TESTING'] = True
    return application


@pytest.fixture
def setup(client, auth_headers, collector):
    headers = auth_headers(2, 1)
    response = client.post(API, json={'name': 'Shop'}, headers=headers)
    assert response.status_code == 201, response.get_json()
    project_id = response.get_json()['id']
    base = f'{API}/{project_id}'
    response = client.post(base + '/checks', json={'name': 'Catalog', 'code': 'catalog.load', 'definition': definition()}, headers=headers)
    assert response.status_code == 201, response.get_json()
    check_id = response.get_json()['id']
    key_body = {'name': 'Release', 'checks': ['catalog.load'], 'environments': ['production'],
                'origins': ['https://shop.example'], 'allow_no_origin': True}
    response = client.post(base + '/keys', json=key_body, headers=headers)
    assert response.status_code == 201, response.get_json()
    key = response.get_json()
    yield {'project': project_id, 'base': base, 'check': check_id, 'key': key, 'headers': headers,
           'key_body': key_body, 'collector': collector.test_client()}
    ClientProject.delete().where(ClientProject.id == project_id).execute()


def send(setup, events, **kwargs):
    return setup['collector'].post(INGEST, json={'schema_version': 1, 'project_key': setup['key']['project_key'],
                                               'events': events}, **kwargs)


def counts(project_id):
    return (ClientReceipt.select().where(ClientReceipt.project == project_id).count(),
            ClientObservation.select().where(ClientObservation.project == project_id).count())


def test_create_send_and_read_with_three_platforms(client, setup):
    values = [event(context={'environment': 'production', 'platform': platform})
              for platform in ['browser', 'windows', 'android']]
    response = send(setup, values)
    assert response.status_code == 202, response.get_json()
    assert response.get_json() == {'schema_version': 1, 'accepted': 3, 'duplicates': 0}
    assert counts(setup['project']) == (3, 3)
    response = client.get(setup['base'] + '/events?limit=2', headers=setup['headers'])
    assert response.status_code == 200
    page = response.get_json()
    assert len(page['items']) == 2
    second = client.get(setup['base'] + f'/events?before_id={page["next_before_id"]}', headers=setup['headers']).get_json()
    assert len(second['items']) == 1
    assert len({row['event']['context']['platform'] for row in page['items'] + second['items']}) == 3
    assert ClientKey.get_by_id(setup['key']['id']).last_used_us is not None
    assert ClientDirtyInterval.select().join(ClientDefinition).where(ClientDefinition.check == setup['check']).exists()


def test_key_is_shown_once_and_never_stored_or_returned_in_lists(client, setup):
    key = setup['key']['project_key']
    stored = ClientKey.get_by_id(setup['key']['id'])
    assert stored.token_hash == service.token_hash(key)
    assert key not in repr(stored.__data__)
    response = client.get(setup['base'] + '/keys', headers=setup['headers'])
    assert response.status_code == 200
    assert key not in response.get_data(as_text=True)
    assert 'token_hash' not in response.get_data(as_text=True)
    assert key not in ''.join(row.action or '' for row in ActionHistory.select())
    assert response.headers['Cache-Control'] == 'no-store'


def test_idempotency_survives_retry_new_key_numeric_and_time_normalization(client, setup):
    original = event(observed_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    assert send(setup, [original, original]).get_json()['accepted'] == 1
    canonical = copy.deepcopy(original)
    canonical['duration_ms'] = 243.0
    canonical['metrics']['items'] = 48.0
    canonical['event_id'] = original['event_id'].upper()
    parsed = datetime.fromisoformat(original['observed_at'])
    canonical['observed_at'] = parsed.astimezone(timezone(timedelta(hours=3))).isoformat()
    issued = client.post(setup['base'] + '/keys', json=setup['key_body'], headers=setup['headers']).get_json()
    setup['key'] = issued
    assert send(setup, [canonical]).status_code == 200
    assert counts(setup['project']) == (1, 1)


@pytest.mark.parametrize('existing', [False, True])
def test_conflicting_event_rolls_back_whole_batch(setup, existing):
    original = event()
    changed = dict(original, duration_ms=999)
    if existing:
        assert send(setup, [original]).status_code == 202
    response = send(setup, [event(), original, changed])
    assert response.status_code == 409
    assert counts(setup['project']) == ((1, 1) if existing else (0, 0))


@pytest.mark.parametrize('changes', [
    {'metrics': {'unexpected': 1}}, {'metrics': {}}, {'metrics': {'items': True}},
    {'metrics': {'items': None}}, {'metrics': {'items': 1.5}}, {'metrics': {'items': 2 ** 53}},
    {'duration_ms': -1}, {'duration_ms': None}, {'status': None}, {'error': {'code': 'failure'}},
    {'context': {'environment': 'production', 'region': 'XX'}},
    {'context': {'environment': 'production', 'platform': False}},
    {'context': {'environment': 'production', 'undefined': 'value'}},
    {'observed_at': '2026-01-01T00:00:00'}, {'event_id': 'not-a-uuid'}, {'definition_version': True},
    {'definition_version': 999}, {'group_id': 99},
], ids=['unknown', 'missing', 'boolean', 'null', 'fraction', 'overflow', 'negative-duration', 'null-duration',
        'null-status', 'error-on-success', 'enum', 'platform-type', 'unknown-context', 'naive-time',
        'uuid', 'version-type', 'version-missing', 'tenant-in-payload'])
def test_invalid_event_rejects_complete_batch(setup, changes):
    response = send(setup, [event(), event(**changes)])
    assert response.status_code == 422, response.get_json()
    assert counts(setup['project']) == (0, 0)


@pytest.mark.parametrize('offset', [-86401, 301])
def test_timestamp_limits_use_server_time(setup, monkeypatch, offset):
    now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(service, 'database_us', lambda: int(now.timestamp()) * 1000000)
    response = send(setup, [event(observed_at=(now + timedelta(seconds=offset)).isoformat())])
    assert response.status_code == 422
    assert counts(setup['project']) == (0, 0)


def test_microsecond_timestamp_is_preserved(setup):
    item = event(observed_at=datetime.now(timezone.utc).replace(microsecond=123456).isoformat())
    assert send(setup, [item]).status_code == 202
    stored = ClientObservation.get(ClientObservation.project == setup['project'])
    assert stored.observed_us % 1000000 == 123456
    assert stored.event['observed_at'].endswith('.123456Z')


def test_measurement_without_outcome(client, setup):
    body = {'code': 'temperature', 'name': 'Temperature', 'definition': {
        'has_outcome': False, 'metrics': {'value': {'label': 'Temperature', 'unit': 'C', 'required': True}},
        'primary_metric': 'value'}}
    assert client.post(setup['base'] + '/checks', json=body, headers=setup['headers']).status_code == 201
    key_body = dict(setup['key_body'], checks=['temperature'])
    setup['key'] = client.post(setup['base'] + '/keys', json=key_body, headers=setup['headers']).get_json()
    value = event(check='temperature', metrics={'value': -12.5})
    value.pop('status')
    value.pop('duration_ms')
    value['context'].pop('region')
    assert send(setup, [value]).status_code == 202
    value['event_id'] = str(uuid4())
    value['status'] = 'ok'
    assert send(setup, [value]).status_code == 422


def test_versions_are_immutable_and_old_versions_remain_usable(client, setup):
    url = setup['base'] + f'/checks/{setup["check"]}/definitions'
    old = client.get(url, headers=setup['headers']).get_json()['items'][0]
    changed = definition()
    changed['metrics']['bytes'] = {'label': 'Bytes', 'unit': 'bytes'}
    response = client.post(url, json=changed, headers=setup['headers'])
    assert response.status_code == 201
    assert response.get_json()['version'] == 2
    assert client.get(url, headers=setup['headers']).get_json()['items'][0] == old
    assert send(setup, [event(), event(definition_version=2, metrics={'items': 48, 'bytes': 12})]).status_code == 202
    changed['metrics']['items']['unit'] = 'ms'
    assert client.post(url, json=changed, headers=setup['headers']).status_code == 409
    assert ClientCheck.get_by_id(setup['check']).current_version == 2


def test_definition_save_detects_another_edit_without_creating_a_version(client, setup):
    url = setup['base'] + f'/checks/{setup["check"]}/definitions'
    headers = dict(setup['headers'], **{'If-Match': '"1"'})
    assert client.post(url, json=definition(), headers=headers).status_code == 201
    stale = client.post(url, json=definition(), headers=headers)
    assert stale.status_code == 409
    assert stale.get_json()['error'] == 'definition_changed'
    assert ClientCheck.get_by_id(setup['check']).current_version == 2
    assert ClientDefinition.select().where(ClientDefinition.check == setup['check']).count() == 2
    headers['If-Match'] = '"2"'
    assert client.post(url, json=definition(), headers=headers).status_code == 201


@pytest.mark.parametrize('value', ['*', '"abc"', '0', '101', '1,2', '"1', '1"', '""1""'])
def test_definition_save_rejects_invalid_precondition(client, setup, value):
    url = setup['base'] + f'/checks/{setup["check"]}/definitions'
    response = client.post(url, json=definition(), headers=dict(setup['headers'], **{'If-Match': value}))
    assert response.status_code == 422
    assert ClientCheck.get_by_id(setup['check']).current_version == 1


def test_revoke_rotate_and_pause(client, setup):
    key = setup['key']
    value = event()
    assert send(setup, [value]).status_code == 202
    assert client.delete(setup['base'] + f'/keys/{key["id"]}', headers=setup['headers']).status_code == 204
    assert client.delete(setup['base'] + f'/keys/{key["id"]}', headers=setup['headers']).status_code == 204
    assert send(setup, [event()]).status_code == 401
    setup['key'] = client.post(setup['base'] + '/keys', json=setup['key_body'], headers=setup['headers']).get_json()
    assert send(setup, [value]).status_code == 200
    assert client.patch(setup['base'], json={'enabled': False}, headers=setup['headers']).status_code == 200
    assert send(setup, [event()]).status_code == 403
    assert client.patch(setup['base'], json={'enabled': True}, headers=setup['headers']).status_code == 200
    assert send(setup, [event()]).status_code == 202


def test_revoke_between_authentication_and_transaction_is_seen(client, setup, monkeypatch):
    original = service.lock_project
    def revoke_before_lock(project_id):
        ClientKey.update(revoked=True).where(ClientKey.id == setup['key']['id']).execute()
        return original(project_id)
    monkeypatch.setattr(service, 'lock_project', revoke_before_lock)
    assert send(setup, [event()]).status_code == 401
    assert counts(setup['project']) == (0, 0)


def test_cross_tenant_access_and_read_only_role(client, setup, auth_headers):
    foreign = Groups.create(group_id=70001, name='client-tenant-' + uuid4().hex)
    other = ClientProject.create(group=foreign.group_id, name='Foreign', created_us=0)
    try:
        for method, suffix, body in [('GET', '', None), ('GET', '/keys', None), ('GET', '/events', None),
                                     ('POST', '/keys', setup['key_body']), ('PATCH', '', {'enabled': False})]:
            response = client.open(f'{API}/{other.id}{suffix}', method=method, json=body, headers=setup['headers'])
            assert response.status_code == 404
        assert client.post(API, json={'name': 'Forbidden', 'group_id': foreign.group_id}, headers=setup['headers']).status_code == 403
        assert client.get(f'{API}?group_id={foreign.group_id}', headers=setup['headers']).status_code == 403
        guest = auth_headers(3, 1)
        assert client.get(setup['base'] + '/events', headers=guest).status_code == 200
        assert client.post(setup['base'] + '/keys', json=setup['key_body'], headers=guest).status_code == 403
        assert client.get(setup['base'], headers=auth_headers(2, foreign.group_id)).status_code in (401, 403)
        assert client.get(f'{API}/{other.id}', headers=auth_headers(1, 1)).status_code == 200
    finally:
        other.delete_instance()
        foreign.delete_instance()


def test_public_key_cannot_read_and_collector_does_not_expose_admin_or_agent_routes(client, setup):
    assert client.get(setup['base'] + '/events', headers={'Authorization': 'Bearer ' + setup['key']['project_key']}).status_code in (401, 422)
    for path in [API, '/api/v1.0/rmon/agent', '/metrics', '/login']:
        assert setup['collector'].get(path).status_code == 404
    assert client.post(INGEST, json={}).status_code in (401, 404)


def test_browser_preflight_beacon_and_origin_restrictions(client, setup):
    headers = {'Origin': 'https://shop.example', 'Access-Control-Request-Method': 'POST',
               'Access-Control-Request-Headers': 'content-type'}
    response = setup['collector'].options(INGEST, headers=headers)
    assert response.status_code == 204
    assert response.headers['Access-Control-Allow-Origin'] == 'https://shop.example'
    raw = json.dumps({'schema_version': 1, 'project_key': setup['key']['project_key'], 'events': [event()]})
    response = setup['collector'].post(INGEST, data=raw, content_type='text/plain;charset=UTF-8', headers=headers)
    assert response.status_code == 202
    assert response.headers['Access-Control-Allow-Origin'] == 'https://shop.example'
    assert 'Access-Control-Allow-Credentials' not in response.headers
    response = send(setup, [event()], headers={'Origin': 'https://other.example'})
    assert response.status_code == 403
    assert 'Access-Control-Allow-Origin' not in response.headers
    key_body = dict(setup['key_body'], allow_no_origin=False)
    setup['key'] = client.post(setup['base'] + '/keys', json=key_body, headers=setup['headers']).get_json()
    assert send(setup, [event()]).status_code == 403
    assert send(setup, [event()], headers={'Origin': 'https://shop.example'}).status_code == 202


def test_scope_is_enforced_for_every_event(setup):
    response = send(setup, [event(), event(context={'environment': 'staging'})])
    assert response.status_code == 403
    assert counts(setup['project']) == (0, 0)
    assert send(setup, [event(check='another.check')]).status_code == 403


@pytest.mark.parametrize('raw,content_type,status', [
    ('{}', 'application/octet-stream', 415), ('{', 'application/json', 400),
    ('{"x": 1, "x": 2}', 'application/json', 400), ('{"x": NaN}', 'application/json', 400),
    ('[]', 'application/json', 422), ('[' * 2000, 'application/json', 400),
    ('x' * (48 * 1024 + 1), 'text/plain', 413),
], ids=['media', 'malformed', 'duplicate-field', 'nan', 'array', 'nested', 'oversized'])
def test_wire_validation(setup, raw, content_type, status):
    assert setup['collector'].post(INGEST, data=raw, content_type=content_type).status_code == status
    assert counts(setup['project']) == (0, 0)


def test_batch_size_and_safe_errors(setup):
    response = send(setup, [event() for _ in range(51)])
    assert response.status_code == 422
    assert setup['key']['project_key'] not in response.get_data(as_text=True)
    assert counts(setup['project']) == (0, 0)


def test_quota_is_atomic_resets_and_retry_is_counted(setup, monkeypatch):
    now = service.database_us() // 60000000 * 60000000
    monkeypatch.setattr(service, 'database_us', lambda: now)
    ClientProject.update(events_per_minute=1, requests_per_minute=2).where(ClientProject.id == setup['project']).execute()
    value = event(observed_at=datetime.fromtimestamp(now / 1000000, timezone.utc).isoformat())
    assert send(setup, [value]).status_code == 202
    assert send(setup, [value]).status_code == 200
    response = send(setup, [event()])
    assert response.status_code == 429
    assert int(response.headers['Retry-After']) > 0
    assert counts(setup['project']) == (1, 1)
    monkeypatch.setattr(service, 'database_us', lambda: now + 60000000)
    assert send(setup, [event()]).status_code == 202


def test_partial_write_failure_rolls_back_receipts_and_observations(setup, monkeypatch, caplog):
    failed = Mock(side_effect=OperationalError('sensitive-database-value'))
    with monkeypatch.context() as patch:
        patch.setattr(service.ClientDirtyInterval, 'create', failed)
        response = send(setup, [event()])
    assert response.status_code == 503
    assert counts(setup['project']) == (0, 0)
    assert 'sensitive-database-value' not in response.get_data(as_text=True)
    assert 'sensitive-database-value' not in caplog.text
    assert send(setup, [event()]).status_code == 202


def test_concurrent_identical_batches_are_counted_once(setup, collector):
    payload = {'schema_version': 1, 'project_key': setup['key']['project_key'], 'events': [event() for _ in range(3)]}
    def submit(_):
        with collector.test_client() as browser:
            response = browser.post(INGEST, json=payload)
            return response.status_code, response.get_json()
    conn.close()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(submit, range(6)))
    assert sorted(status for status, _ in results) == [200] * 5 + [202], results
    assert sum(body['accepted'] for _, body in results) == 3
    assert counts(setup['project']) == (3, 3)


def test_migration_is_repeatable_and_preserves_history(setup):
    assert send(setup, [event()]).status_code == 202
    path = Path(__file__).parents[2] / 'app/migrations/20260927000000_add_client_telemetry.py'
    spec = importlib.util.spec_from_file_location('telemetry_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
    module.upgrade()
    assert counts(setup['project']) == (1, 1)
    assert set(model._meta.table_name for model in CLIENT_TABLES) <= set(conn.get_tables())
    with pytest.raises(RuntimeError, match='retained'):
        module.downgrade()


def test_postgres_does_not_reconnect_inside_transaction(monkeypatch):
    from psycopg2 import OperationalError as DriverError
    from app.modules.db.db_model import SafePooledPostgresqlExtDatabase, PooledPostgresqlExtDatabase
    database = SafePooledPostgresqlExtDatabase('unused')
    execute = Mock(side_effect=DriverError('connection lost'))
    monkeypatch.setattr(PooledPostgresqlExtDatabase, 'execute_sql', execute)
    monkeypatch.setattr(database, 'in_transaction', lambda: True)
    reconnect = Mock()
    monkeypatch.setattr(database, 'connect', reconnect)
    with pytest.raises(DriverError):
        database.execute_sql('SELECT 1')
    reconnect.assert_not_called()
    assert execute.call_count == 1


def test_status_only_check(client, setup):
    body = {'code': 'available', 'name': 'Availability', 'definition': {'has_outcome': True}}
    assert client.post(setup['base'] + '/checks', json=body, headers=setup['headers']).status_code == 201
    setup['key'] = client.post(setup['base'] + '/keys', json=dict(setup['key_body'], checks=['available']),
                               headers=setup['headers']).get_json()
    value = event(check='available', metrics={}, context={'environment': 'production'})
    value.pop('duration_ms')
    assert send(setup, [value]).status_code == 202


@pytest.mark.parametrize('value', ['\x00', '\ud800', '\udfff'])
def test_nonportable_unicode_is_rejected_on_every_database(setup, value):
    raw = json.dumps({'schema_version': 1, 'project_key': setup['key']['project_key'],
                      'events': [event(context={'environment': 'production', 'region': value})]})
    response = setup['collector'].post(INGEST, data=raw, content_type='application/json')
    assert response.status_code == 400
    assert counts(setup['project']) == (0, 0)


@pytest.mark.parametrize('origin', ['null', 'https://shop.example/path', 'https://bad.example:abc'])
def test_invalid_preflight_origin_is_rejected(setup, origin):
    response = setup['collector'].options(INGEST, headers={'Origin': origin, 'Access-Control-Request-Method': 'POST'})
    assert response.status_code == 403


def test_invalid_definition_has_no_partial_check(client, setup):
    before = ClientCheck.select().where(ClientCheck.project == setup['project']).count()
    response = client.post(setup['base'] + '/checks', json={'name': 'Bad', 'code': 'bad', 'definition': {
        'has_outcome': False, 'duration': {'label': 'Delay', 'unit': 'seconds', 'minimum': 0}}}, headers=setup['headers'])
    assert response.status_code == 422
    assert ClientCheck.select().where(ClientCheck.project == setup['project']).count() == before


def test_real_database_rolls_back_before_commit(setup):
    from app.modules.client_telemetry import service as management
    project_id = setup['project']
    before = ClientProject.get_by_id(project_id).revision
    with pytest.raises(RuntimeError, match='abort'):
        with conn.atomic():
            management.lock_project(project_id)
            ClientReceipt.create(project=project_id, event_id=str(uuid4()), content_hash='0' * 64, received_us=0)
            raise RuntimeError('abort')
    assert ClientProject.get_by_id(project_id).revision == before
    assert counts(project_id) == (0, 0)


def test_migration_creates_missing_tables_and_resumes_after_partial_ddl(monkeypatch):
    from app.modules.client_telemetry.models import ClientDirtyInterval
    path = Path(__file__).parents[2] / 'app/migrations/20260927000000_add_client_telemetry.py'
    spec = importlib.util.spec_from_file_location('telemetry_migration_partial', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    # This fixture database is disposable. Other telemetry tables remain intact.
    conn.drop_tables([ClientDirtyInterval])
    assert not ClientDirtyInterval.table_exists()
    migration.upgrade()
    migration.upgrade()
    assert ClientDirtyInterval.table_exists()


def test_migration_repairs_missing_deduplication_index(setup):
    from playhouse.migrate import migrate
    path = Path(__file__).parents[2] / 'app/migrations/20260927000000_add_client_telemetry.py'
    spec = importlib.util.spec_from_file_location('telemetry_migration_index', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    index = next(index for index in conn.get_indexes('client_receipts')
                 if index.unique and tuple(index.columns) == ('project_id', 'event_id'))
    migrate(connect(get_migrator=True).drop_index('client_receipts', index.name))
    migration.upgrade()
    row = {'project': setup['project'], 'event_id': str(uuid4()), 'content_hash': '0' * 64, 'received_us': 0}
    ClientReceipt.create(**row)
    with pytest.raises(IntegrityError):
        with conn.atomic():
            ClientReceipt.create(**row)


def test_full_unicode_round_trip(client, setup):
    name = 'Магазин \U0001f3ae'
    created = client.post(API, json={'name': name}, headers=setup['headers'])
    assert created.status_code == 201, created.get_json()
    project_id = created.get_json()['id']
    try:
        response = client.get(f'{API}/{project_id}', headers=setup['headers'])
        assert response.get_json()['name'] == name
        assert ClientProject.get_by_id(project_id).name == name
        if isinstance(conn, MySQLDatabase):
            cursor = conn.execute_sql('SHOW TABLE STATUS LIKE %s', ('client_projects',))
            details = dict(zip([column[0] for column in cursor.description], cursor.fetchone()))
            assert details['Engine'] == 'InnoDB'
            assert details['Collation'].startswith('utf8mb4_')
    finally:
        ClientProject.delete().where(ClientProject.id == project_id).execute()


def test_out_of_range_identifiers_are_rejected_before_database_lookup(client, setup):
    enormous = str(2 ** 100)
    response = client.post(API, json={'name': 'Invalid', 'group_id': int(enormous)}, headers=setup['headers'])
    assert response.status_code == 422
    assert client.get(f'{API}/{enormous}', headers=setup['headers']).status_code == 404
    assert client.get(setup['base'] + f'/checks/{enormous}/definitions', headers=setup['headers']).status_code == 404
    assert client.delete(setup['base'] + f'/keys/{enormous}', headers=setup['headers']).status_code == 404
