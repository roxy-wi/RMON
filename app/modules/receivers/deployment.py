"""Queue server operations with private configuration snapshots."""
import configparser
import base64
import hashlib
import io
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import uuid4

from peewee import IntegrityError

from app.modules.db.db_model import InstallationTasks, OperationJob, Server, Setting
from app.modules.operations.queue import enqueue
from app.modules.receivers.models import ResultServer, ResultServerEndpoint
from app.modules.receivers import service
from app.modules.roxy_wi_tools import GetConfigVar


def metadata():
    config = GetConfigVar().config
    for section, prefix, default_port in (('pgsql', '', 5432), ('mysql', 'mysql_', 3306)):
        if config.get(section, 'enable', fallback='0') == '1':
            return {'transport': config.get('server_deployment', 'transport', fallback='http'),
                    'database_type': 'postgresql' if section == 'pgsql' else 'mysql',
                    'database_host': config.get(section, prefix + 'host'),
                    'database_port': config.getint(section, prefix + 'port', fallback=default_port)}
    return {'transport': config.get('server_deployment', 'transport', fallback='http'),
            'database_type': 'sqlite', 'database_host': '', 'database_port': None}


def deployment_identity():
    Setting.insert(param='server_deployment_id', group_id=1, value=str(uuid4()), section='rmon', desc='').on_conflict_ignore().execute()
    return Setting.get((Setting.param == 'server_deployment_id') & (Setting.group_id == 1)).value


def inventory(server, action):
    host = server.host
    values = {'action': action, 'result_server_id': server.id, 'result_server_uuid': server.uuid,
              'result_server_revision': server.revision, 'result_server_roles': server.roles}
    if action == 'install':
        source = GetConfigVar().config
        meta = metadata()
        if meta['database_type'] == 'sqlite':
            if not server.sqlite_path:
                service.fail(422, 'sqlite_path_required', 'Specify the existing shared SQLite database path on this host; a remote copy cannot be used')
            database_url = 'sqlite:////var/lib/rmon-shared/' + PurePosixPath(server.sqlite_path).name
            values['result_server_sqlite_path'] = server.sqlite_path
        else:
            section, prefix = ('pgsql', '') if meta['database_type'] == 'postgresql' else ('mysql', 'mysql_')
            address = server.database_host or meta['database_host']
            if ':' in address:
                address = f'[{address}]'
            database_url = (f"{meta['database_type']}://{quote(source.get(section, prefix + 'user'), safe='')}:"
                            f"{quote(source.get(section, prefix + 'password'), safe='')}@{address}:"
                            f"{server.database_port or meta['database_port']}/{quote(source.get(section, prefix + 'db'), safe='')}")
        config = configparser.ConfigParser(interpolation=None)
        config['rmon-server'] = {
            'roles': ','.join(server.roles), 'database_url': database_url,
            'bind': '0.0.0.0:5100', 'client_bind': '0.0.0.0:5102',
            'workers': '1', 'threads': '4', 'client_workers': '1', 'client_threads': '4',
            'internal_api_token': secrets.token_urlsafe(32), 'log_path': '-',
        }
        # Transport files are operator-controlled paths on the target SSH host.
        # A client collector may sit behind a separate HTTPS load balancer.
        certificate_files = []
        options = ('transport', 'internal_api_token_file', 'tls_cert_file', 'tls_key_file', 'tls_ca_file',
                   'probe_ca_file', 'probe_client_cert_file', 'probe_client_key_file',
                   'client_trusted_proxies', 'client_geoip_database')
        for key in options:
            value = source.get('server_deployment', key, fallback='')
            if value:
                if key.endswith('_file') or key == 'client_geoip_database':
                    if not value.startswith('/') or any(c in value for c in '\n\r\x00{}') or '..' in value.split('/'):
                        service.fail(422, 'deployment_configuration', 'Server certificate and GeoIP paths must be absolute paths on the target host')
                    target = '/etc/rmon/managed/' + key
                    certificate_files.append({'source': value, 'name': key})
                    value = target
                option = 'client_geoip_db' if key == 'client_geoip_database' else key
                config['rmon-server'][option] = value
        output = io.StringIO()
        config.write(output)
        image = os.getenv('RMON_SERVER_IMAGE') or source.get('server_deployment', 'image', fallback='ghcr.io/roxy-wi/rmon/rmon-server:7.0')
        ports = ([f'{server.bind_ip}:{server.classic_port}:5100'] if 'classic' in server.roles else [])
        ports += ([f'{server.bind_ip}:{server.client_port}:5102'] if 'client' in server.roles else [])
        # Encoding prevents Ansible interpreting braces in database credentials.
        values.update(result_server_config_b64=base64.b64encode(output.getvalue().encode()).decode(), result_server_image=image,
                      result_server_ports=ports, result_server_files=certificate_files,
                      result_server_database_identity=deployment_identity())
        values['result_server_hash'] = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    return {'server': {'hosts': {host.ip: values}}}, [host.ip]


def get_server(server_id, group_id, admin=False):
    server = ResultServer.get_or_none(ResultServer.id == server_id)
    if server is None or (not admin and int(server.host.group_id) != int(group_id)):
        service.fail(404, 'server_not_found', 'Result server was not found')
    return server


def ensure_idle(server):
    if OperationJob.select().where((OperationJob.server == server.host_id) &
                                   OperationJob.status.in_(('queued', 'running'))).exists():
        service.fail(409, 'operation_pending', 'Wait for the current operation on this host to finish')


def ensure_detachable(server, remaining_ids):
    from app.modules.receivers.models import AgentReceiver, AppliedAgentReceiver, PendingAgentReceiver, GroupReceiver, ProjectReceiver
    for binding in ResultServerEndpoint.select().where((ResultServerEndpoint.server == server.id) &
                                                        ResultServerEndpoint.endpoint.not_in(remaining_ids)):
        address = binding.endpoint
        if any(model.select().where(model.endpoint == address.id).exists()
               for model in (AgentReceiver, AppliedAgentReceiver, PendingAgentReceiver, GroupReceiver, ProjectReceiver)):
            replacements = ResultServer.select().join(ResultServerEndpoint).where(
                (ResultServerEndpoint.endpoint == address.id) & (ResultServer.id != server.id) &
                (ResultServer.state == 'ready'))
            available = False
            for replacement in replacements:
                draining = OperationJob.select().join(InstallationTasks).where(
                    (OperationJob.server == replacement.host_id) & OperationJob.status.in_(('queued', 'running')) &
                    InstallationTasks.action.in_(('stop', 'delete', 'reconfigure'))).exists()
                if address.role in replacement.applied_roles and not draining:
                    available = True
                    break
            if not available:
                service.fail(409, 'server_in_use', 'Assign a replacement server or remove consumers before disconnecting the last server')


def configure(body, group_id, user_id, server_id=None):
    try:
        with service.transaction():
            host = Server.get_or_none(Server.server_id == body.host_id)
            if host is None:
                service.fail(404, 'host_not_found', 'The installation host was not found')
            Server.update(hostname=Server.hostname).where(Server.server_id == host.server_id).execute()
            server = get_server(server_id, group_id, admin=True) if server_id else None
            data = body.model_dump(exclude={'host_id', 'endpoint_ids', 'new_endpoints', 'revision'})
            if server:
                if server.host_id != body.host_id:
                    service.fail(422, 'host_immutable', 'An installed server cannot be moved to another host')
                ensure_idle(server)
                if body.revision != server.revision:
                    service.fail(409, 'revision_conflict', 'The server changed; reload its settings')
                ResultServer.update(**data, revision=ResultServer.revision + 1).where(ResultServer.id == server.id).execute()
                server = ResultServer.get_by_id(server.id)
            else:
                if ResultServer.select().where(ResultServer.host == host.server_id).exists():
                    service.fail(409, 'server_exists', 'A result server is already registered on this host')
                server = ResultServer.create(host=host.server_id, uuid=str(uuid4()), **data)
                ensure_idle(server)
            ids = list(body.endpoint_ids)
            for endpoint_body in body.new_endpoints:
                ids.append(service.save_endpoint(endpoint_body, int(host.group_id), admin=True).id)
            values = service.selected_endpoints(ids, host.group_id)
            old = [link.endpoint for link in ResultServerEndpoint.select().where(ResultServerEndpoint.server == server.id)]
            service.lock_endpoints({e.id: e for e in [*old, *values]}.values())
            values = service.selected_endpoints(ids, host.group_id)
            if any(e.role not in body.roles for e in values):
                service.fail(422, 'receiver_role', 'Enable the server role required by each assigned receiver address')
            config = GetConfigVar().config
            direct_mode = config.get('server_deployment', 'transport', fallback='http')
            for value in values:
                if value.kind == 'direct' and ResultServerEndpoint.select().where(
                        (ResultServerEndpoint.endpoint == value.id) & (ResultServerEndpoint.server != server.id)).exists():
                    service.fail(409, 'receiver_in_use', 'Use a load balancer address to connect multiple servers')
                if value.kind == 'direct' and value.transport != ('http' if value.role == 'client' else direct_mode):
                    service.fail(422, 'server_transport', 'A direct receiver must use the server transport; use a load balancer address for HTTPS termination')
            ensure_detachable(server, ids)
            ResultServerEndpoint.delete().where(ResultServerEndpoint.server == server.id).execute()
            for value in values:
                ResultServerEndpoint.create(server=server.id, endpoint=value.id)
            inv, ips = inventory(server, 'install')
            task_id = enqueue(inv, ips, 'rmon_server', 'Result server', 'reconfigure' if server_id else 'install', user_id)
            return server, task_id
    except IntegrityError:
        service.fail(409, 'server_conflict', 'The host or receiver assignment already exists; reload the page')


def action(server, operation, user_id):
    if operation not in ('start', 'stop', 'restart', 'check', 'uninstall'):
        service.fail(422, 'invalid_action', 'Select a supported server action')
    with service.transaction():
        Server.update(hostname=Server.hostname).where(Server.server_id == server.host_id).execute()
        ensure_idle(server)
        if operation in ('stop', 'uninstall'):
            service.lock_endpoints(link.endpoint for link in ResultServerEndpoint.select().where(ResultServerEndpoint.server == server.id))
            ensure_detachable(server, [])
        inv, ips = inventory(server, operation)
        return enqueue(inv, ips, 'rmon_server', 'Result server', 'delete' if operation == 'uninstall' else operation, user_id)


def record_applied(inv):
    for value in inv.get('server', {}).get('hosts', {}).values():
        server_id = value.get('result_server_id')
        if not server_id:
            continue
        query = (ResultServer.id == server_id) & (ResultServer.uuid == value['result_server_uuid'])
        if value['action'] == 'uninstall':
            ResultServer.delete().where(query).execute()
        else:
            changes = {'state': 'stopped' if value['action'] == 'stop' else 'ready',
                       'checked_at': datetime.now(timezone.utc).replace(tzinfo=None)}
            if value['action'] == 'install':
                changes.update(applied_revision=value['result_server_revision'],
                               applied_roles=value['result_server_roles'], image=value['result_server_image'])
            ResultServer.update(**changes).where(query).execute()


def server_json(server):
    task = InstallationTasks.select().where((InstallationTasks.server_id == server.host_id) &
                                             (InstallationTasks.service_name == 'Result server')).order_by(InstallationTasks.id.desc()).first()
    data = {name: getattr(server, name) for name in ('id', 'name', 'host_id', 'roles', 'classic_port', 'client_port',
            'bind_ip', 'database_host', 'database_port', 'sqlite_path', 'revision', 'applied_revision', 'applied_roles', 'image', 'state')}
    data.update(hostname=server.host.hostname, ip=server.host.ip, group_id=int(server.host.group_id),
                endpoint_ids=[r.endpoint_id for r in ResultServerEndpoint.select().where(ResultServerEndpoint.server == server.id)],
                checked_at=server.checked_at.isoformat() + 'Z' if server.checked_at else None,
                task={'id': task.id, 'status': task.status, 'action': task.action, 'error': task.error} if task else None)
    return data
