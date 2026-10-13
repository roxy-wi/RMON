"""Receiver ownership, routing snapshots and operation state."""
import hashlib
import json
from datetime import datetime, timezone

from peewee import IntegrityError, MySQLDatabase

from app.modules.client_telemetry.service import TelemetryError
from app.modules.db.db_model import Groups, InstallationTasks, SmonAgent, conn
from app.modules.client_telemetry.models import ClientProject
from app.modules.receivers.models import (AgentReceiver, AgentRouting, GroupReceiver, ProjectReceiver,
                                         ReceiverEndpoint, ResultServerEndpoint, AppliedAgentReceiver, PendingAgentReceiver)


def fail(status, code, message):
    raise TelemetryError(status, code, message)


def transaction():
    # Re-read assignments after waiting on endpoint locks. MySQL's default
    # snapshot isolation could otherwise hide a newly queued stop or assignment.
    return conn.atomic(**({'isolation_level': 'READ COMMITTED'} if isinstance(conn, MySQLDatabase) else {}))


def endpoint(endpoint_id, group_id, *, owner=False, admin=False):
    value = ReceiverEndpoint.get_or_none(ReceiverEndpoint.id == endpoint_id)
    if value is None or (not admin and value.group_id != int(group_id) and (owner or not value.shared)):
        fail(404, 'receiver_not_found', 'Receiver address was not found')
    return value


def endpoint_json(value):
    data = {name: getattr(value, name) for name in ('id', 'group_id', 'name', 'url', 'role', 'transport',
                                                  'kind', 'shared', 'revision')}
    data['server_ids'] = [row.server_id for row in ResultServerEndpoint.select().where(
        ResultServerEndpoint.endpoint == value.id)]
    data['agent_count'] = len({row.agent_id for model in (AgentReceiver, AppliedAgentReceiver, PendingAgentReceiver)
                              for row in model.select(model.agent).where(model.endpoint == value.id)})
    data['project_count'] = ProjectReceiver.select().where(ProjectReceiver.endpoint == value.id).count()
    data['default_group_count'] = GroupReceiver.select().where(GroupReceiver.endpoint == value.id).count()
    return data


def used(value):
    return any(model.select().where(model.endpoint == value.id).exists()
               for model in (AgentReceiver, AppliedAgentReceiver, PendingAgentReceiver, GroupReceiver, ProjectReceiver, ResultServerEndpoint))


def save_endpoint(body, group_id, *, endpoint_id=None, admin=False):
    if body.shared and not admin:
        fail(403, 'administrator_required', 'Only a system administrator can share receiver addresses')
    data = body.model_dump(exclude={'revision'})
    try:
        with transaction():
            if endpoint_id is None:
                return ReceiverEndpoint.create(group=group_id, **data)
            value = endpoint(endpoint_id, group_id, owner=True, admin=admin)
            if body.revision is None:
                fail(422, 'revision_required', 'Reload the receiver address before saving')
            # The compare-and-swap locks the address before examining references.
            changed = ReceiverEndpoint.update(revision=ReceiverEndpoint.revision + 1).where(
                (ReceiverEndpoint.id == value.id) & (ReceiverEndpoint.revision == body.revision)).execute()
            if not changed:
                fail(409, 'revision_conflict', 'The receiver address changed; reload it before saving')
            if (value.role != body.role or (value.shared and not body.shared)) and used(value):
                fail(409, 'receiver_in_use', 'Remove assignments before changing the role or shared access')
            if value.transport != body.transport and ResultServerEndpoint.select().where(
                    ResultServerEndpoint.endpoint == value.id).exists() and value.kind == 'direct':
                fail(409, 'receiver_in_use', 'Configure the server transport before changing its direct address')
            if value.kind != body.kind and ResultServerEndpoint.select().where(
                    ResultServerEndpoint.endpoint == value.id).exists():
                fail(409, 'receiver_in_use', 'Remove server assignments before changing the connection type')
            ReceiverEndpoint.update(**data).where(ReceiverEndpoint.id == value.id).execute()
            return ReceiverEndpoint.get_by_id(value.id)
    except IntegrityError:
        fail(409, 'duplicate_receiver', 'This address is already registered for this role; select the existing address')


def delete_endpoint(value):
    try:
        with transaction():
            value.delete_instance()
    except IntegrityError:
        fail(409, 'receiver_in_use', 'Remove server, agent, project and group assignments before deleting this address')


def selected_endpoints(ids, group_id, role=None):
    values = [endpoint(i, group_id) for i in ids]
    if role and any(e.role != role for e in values):
        fail(422, 'receiver_role', 'Select receiver addresses with the required role')
    return values


def lock_endpoints(values):
    # A stable locking order also prevents an owner removing shared access while
    # another group assigns this endpoint. SQLite serializes these writes.
    for value in sorted(values, key=lambda e: e.id):
        ReceiverEndpoint.update(revision=ReceiverEndpoint.revision).where(ReceiverEndpoint.id == value.id).execute()


def defaults(group_id):
    return [r.endpoint_id for r in GroupReceiver.select().where(GroupReceiver.group == group_id)
            .order_by(GroupReceiver.position, GroupReceiver.id)]


def save_defaults(group_id, ids):
    with transaction():
        Groups.update(name=Groups.name).where(Groups.group_id == group_id).execute()
        values = selected_endpoints(ids or [], group_id, 'classic')
        lock_endpoints(values)
        selected_endpoints(ids or [], group_id, 'classic')
        GroupReceiver.delete().where(GroupReceiver.group == group_id).execute()
        for position, value in enumerate(values):
            GroupReceiver.create(group=group_id, endpoint=value.id, position=position)


def routing_json(agent):
    routing = AgentRouting.get_or_none(AgentRouting.agent == agent.id)
    ids = [r.endpoint_id for r in AgentReceiver.select().where(AgentReceiver.agent == agent.id)
           .order_by(AgentReceiver.position, AgentReceiver.id)]
    return {'endpoint_ids': None if routing is None or routing.inherit else ids,
            'policy': routing.policy if routing else 'balance'}


def effective_routing(group_id, selection):
    ids = selection['endpoint_ids']
    if ids is None:
        ids = defaults(group_id)
        if not ids and int(group_id) != 1:
            ids = [i for i in defaults(1) if endpoint(i, 1).shared]
    values = selected_endpoints(ids, group_id, 'classic')
    result = {'endpoint_ids': [e.id for e in values],
              'endpoints': [{'url': e.url, 'transport': e.transport} for e in values],
              'policy': selection['policy']}
    return result


def routing_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def routing_transport(config, fallback):
    modes = {e['transport'] for e in config['endpoints']}
    return next((mode for mode in ('mtls', 'https', 'http') if mode in modes), fallback)


def save_agent_routing(agent, selection):
    with transaction():
        SmonAgent.update(name=SmonAgent.name).where(SmonAgent.id == agent.id).execute()
        values = selected_endpoints(selection.endpoint_ids or [], agent.server_id.group_id, 'classic')
        lock_endpoints(values)
        selected_endpoints(selection.endpoint_ids or [], agent.server_id.group_id, 'classic')
        row, _ = AgentRouting.get_or_create(agent=agent.id)
        AgentRouting.update(inherit=selection.endpoint_ids is None, policy=selection.policy).where(
            AgentRouting.id == row.id).execute()
        AgentReceiver.delete().where(AgentReceiver.agent == agent.id).execute()
        for position, value in enumerate(values):
            AgentReceiver.create(agent=agent.id, endpoint=value.id, position=position)


def routing_pending(agent):
    if PendingAgentReceiver.select().where(PendingAgentReceiver.agent == agent.id).exists():
        return True
    row = AgentRouting.get_or_none(AgentRouting.agent == agent.id)
    config = effective_routing(agent.server_id.group_id, routing_json(agent))
    if not config['endpoints'] and row is None:
        return False
    return row is None or row.applied_hash != routing_hash(config)


def record_agent_applied(inventory):
    for host in inventory.get('server', {}).get('hosts', {}).values():
        fingerprint = host.get('agent_routing_hash')
        if fingerprint and host.get('action') == 'install':
            agent = SmonAgent.get(SmonAgent.uuid == str(host['agent_uuid']))
            row, _ = AgentRouting.get_or_create(agent=agent.id)
            AgentRouting.update(applied_hash=fingerprint, applied_at=datetime.now(timezone.utc).replace(tzinfo=None)).where(
                AgentRouting.id == row.id).execute()
            AppliedAgentReceiver.delete().where(AppliedAgentReceiver.agent == agent.id).execute()
            for endpoint_id in host.get('agent_receiver_ids', []):
                AppliedAgentReceiver.create(agent=agent.id, endpoint=endpoint_id)
            # A failed SSH operation may have applied its config before losing
            # contact. Keep its addresses protected until a later success.
            finished = InstallationTasks.select(InstallationTasks.id).where(
                InstallationTasks.status.in_(('completed', 'failed')))
            PendingAgentReceiver.delete().where((PendingAgentReceiver.agent == agent.id) &
                                                 PendingAgentReceiver.task.in_(finished)).execute()


def reserve_agent_receivers(task_id, inventory):
    for host in inventory.get('server', {}).get('hosts', {}).values():
        ids = host.get('agent_receiver_ids', [])
        if not ids:
            continue
        agent = SmonAgent.get(SmonAgent.uuid == str(host['agent_uuid']))
        for endpoint_id in ids:
            PendingAgentReceiver.create(task=task_id, agent=agent.id, endpoint=endpoint_id)


def release_agent_receivers(task_id):
    PendingAgentReceiver.delete().where(PendingAgentReceiver.task == task_id).execute()


def project_receiver(project):
    row = ProjectReceiver.get_or_none(ProjectReceiver.project == project.id)
    if row is None:
        return {'endpoint_id': None, 'ingest_url': None}
    value = endpoint(row.endpoint_id, project.group_id)
    return {'endpoint_id': value.id, 'ingest_url': value.url + '/api/v1/client/events'}


def save_project_receiver(project, endpoint_id):
    with transaction():
        ClientProject.update(name=ClientProject.name).where(ClientProject.id == project.id).execute()
        if endpoint_id is not None:
            value = endpoint(endpoint_id, project.group_id)
            lock_endpoints([value])
            value = endpoint(endpoint_id, project.group_id)
            if value.role != 'client':
                fail(422, 'receiver_role', 'Select a receiver for client projects')
        ProjectReceiver.delete().where(ProjectReceiver.project == project.id).execute()
        if endpoint_id is not None:
            ProjectReceiver.create(project=project.id, endpoint=endpoint_id)
    return project_receiver(project)
