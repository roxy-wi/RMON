import uuid

import pytest

import app.modules.db.server as server_sql
from app.modules.db.db_model import Server, SystemInfo


@pytest.mark.security
def test_missing_system_info_returns_false_and_existing_returns_true():
    server = Server.create(
        hostname=f'system-{uuid.uuid4().hex}', ip=f'192.0.2.{uuid.uuid4().int % 200 + 1}',
        group_id='1', enabled=1, cred_id=1, port=22, description='system info test'
    )

    assert server_sql.is_system_info(server.server_id) is False

    SystemInfo.create(
        server_id=server.server_id, os_info='Linux', sys_info='{}', cpu='{}', ram='{}',
        disks='{}', network='{}'
    )
    assert server_sql.is_system_info(server.server_id) is True
