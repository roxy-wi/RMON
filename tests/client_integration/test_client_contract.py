"""Detect incompatible storage and payload changes between independently installed components."""
from pathlib import Path

from client_runtime import root, server_connection
from app.modules.client_telemetry import models, schemas
from app.modules.db.db_model import conn
from modules.client_telemetry import models as server_models, schemas as server_schemas


def test_components_have_independent_connections_to_the_same_database():
    assert conn is not server_connection.conn
    assert conn.database == server_connection.conn.database


def test_persisted_table_mappings_match():
    def contract(model):
        return {
            'table': model._meta.table_name,
            'indexes': model._meta.indexes,
            'fields': {name: (field.column_name, field.field_type, field.null, field.unique,
                             field.primary_key, field.index, getattr(field, 'max_length', None))
                       for name, field in model._meta.fields.items()},
        }
    assert [contract(model) for model in models.CLIENT_TABLES] == [contract(model) for model in server_models.CLIENT_TABLES]


def test_validation_and_histogram_contracts_match():
    assert schemas.Batch.model_json_schema() == server_schemas.Batch.model_json_schema()
    assert schemas.Definition.model_json_schema() == server_schemas.Definition.model_json_schema()
    local = Path(__file__).resolve().parents[2] / 'app/modules/client_telemetry'
    for name in ('schemas.py', 'distributions.py', 'contract.py'):
        before = (local / name).read_text(encoding='utf-8').replace('app.modules.client_telemetry', 'modules.client_telemetry')
        assert before == (root / 'modules/client_telemetry' / name).read_text(encoding='utf-8'), name
