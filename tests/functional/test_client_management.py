import importlib.util
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from peewee import IntegrityError, MySQLDatabase

from app.modules.client_telemetry import service
from app.modules.client_telemetry.models import (
    ClientCheck, ClientDefinition, ClientDirtyInterval, ClientKey,
    ClientObservation, ClientProject, ClientReceipt,
)
from app.modules.db.db_model import ActionHistory, Groups, conn, connect, create_tables

pytestmark = pytest.mark.functional
API = '/api/v1.0/client/projects'
INGEST = '/api/v1/client/events'


def definition():
    return {'has_outcome': True, 'duration': {'label': 'Duration', 'unit': 'ms', 'minimum': 0},
            'primary_metric': 'duration_ms',
            'metrics': {'items': {'label': 'Items', 'unit': 'count', 'type': 'integer', 'required': True}},
            'context': {'region': {'label': 'Region', 'type': 'enum', 'values': ['EU', 'US'], 'filterable': True}}}


@pytest.fixture
def setup(client, auth_headers):
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
           'key_body': key_body}
    ClientProject.delete().where(ClientProject.id == project_id).execute()



def counts(project_id):
    return (ClientReceipt.select().where(ClientReceipt.project == project_id).count(),
            ClientObservation.select().where(ClientObservation.project == project_id).count())


@pytest.mark.parametrize('body,content_type,status,error', [
    ('{"name":"Shop"}', 'text/plain;charset=UTF-8', 415, 'unsupported_media_type'),
    ('{"name":"Shop"}', 'application/json;charset=latin-1', 415, 'unsupported_media_type'),
    ('{"name":"Shop","name":"Other"}', 'application/json', 400, 'invalid_json'),
    ('{"name":"Shop","events_per_minute":NaN}', 'application/json', 400, 'invalid_json'),
    ('{"name":"Shop\\u0000"}', 'application/json', 400, 'invalid_json'),
    (b'\xff', 'application/json', 400, 'invalid_json'),
    ('x' * (48 * 1024 + 1), 'application/json', 413, 'payload_too_large'),
], ids=['plain-text', 'charset', 'duplicate-field', 'nan', 'nul', 'invalid-utf8', 'oversized'])
def test_management_rejects_invalid_json_without_creating_project(client, auth_headers, body, content_type, status, error):
    before = ClientProject.select().count()
    response = client.post(API, data=body, content_type=content_type, headers=auth_headers(2, 1))
    assert response.status_code == status
    assert response.get_json()['error'] == error
    assert ClientProject.select().count() == before



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



def test_invalid_definition_has_no_partial_check(client, setup):
    before = ClientCheck.select().where(ClientCheck.project == setup['project']).count()
    response = client.post(setup['base'] + '/checks', json={'name': 'Bad', 'code': 'bad', 'definition': {
        'has_outcome': False, 'duration': {'label': 'Delay', 'unit': 'seconds', 'minimum': 0}}}, headers=setup['headers'])
    assert response.status_code == 422
    assert ClientCheck.select().where(ClientCheck.project == setup['project']).count() == before



def test_real_database_rolls_back_before_commit(setup):
    project_id = setup['project']
    before = ClientProject.get_by_id(project_id).revision
    with pytest.raises(RuntimeError, match='abort'):
        with conn.atomic():
            service.lock_project(project_id)
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


def test_analytics_migration_preserves_intervals_without_server_runtime(setup):
    from playhouse.migrate import migrate
    definition_id = ClientDefinition.get(ClientDefinition.check == setup['check']).id
    row_id = ClientDirtyInterval.create(definition=definition_id, minute=service.database_us() // 60000000 - 2).id
    fields = ['processed_generation', 'pending', 'owner', 'lease_until_us', 'available_us', 'attempts',
              'last_error', 'last_received_us', 'updated_us', 'raw_deleted']
    migrator = connect(get_migrator=True)

    def load(name):
        path = Path(__file__).parents[2] / 'app/migrations' / name
        spec = importlib.util.spec_from_file_location(name.removesuffix('.py'), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    migration = load('20260927010000_add_client_analytics.py')
    try:
        for index in conn.get_indexes('client_dirty_intervals'):
            if set(index.columns) & set(fields):
                migrate(migrator.drop_index('client_dirty_intervals', index.name))
        for name in fields:
            migrate(migrator.drop_column('client_dirty_intervals', name))
        create_tables()
        load('20260927000000_add_client_telemetry.py').upgrade()
    finally:
        migration.upgrade()
    migration.upgrade()
    row = ClientDirtyInterval.get_by_id(row_id)
    assert row.generation == 1 and row.processed_generation == 0 and row.pending
