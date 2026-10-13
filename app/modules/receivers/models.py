from peewee import AutoField, BooleanField, CharField, DateTimeField, ForeignKeyField, IntegerField, MySQLDatabase

from app.modules.db.db_model import BaseModel, Groups, InstallationTasks, JSONField, Server, SmonAgent, conn
from app.modules.client_telemetry.models import ClientProject


class ReceiverModel(BaseModel):
    class Meta:
        table_settings = ['ENGINE=InnoDB', 'DEFAULT CHARSET=utf8mb4', 'COLLATE=utf8mb4_bin'] if isinstance(conn, MySQLDatabase) else None


class ReceiverEndpoint(ReceiverModel):
    id = AutoField()
    group = ForeignKeyField(Groups, on_delete='CASCADE')
    name = CharField(max_length=160)
    url = CharField(max_length=500)
    role = CharField(max_length=16)
    transport = CharField(max_length=16, default='http')
    kind = CharField(max_length=16, default='direct')
    shared = BooleanField(default=False)
    revision = IntegerField(default=1)

    class Meta:
        table_name = 'receiver_endpoints'
        indexes = ((('group', 'role', 'url'), True),)


class ResultServer(ReceiverModel):
    id = AutoField()
    host = ForeignKeyField(Server, unique=True, on_delete='RESTRICT')
    uuid = CharField(max_length=36, unique=True)
    name = CharField(max_length=160)
    roles = JSONField()
    classic_port = IntegerField(default=5100)
    client_port = IntegerField(default=5102)
    bind_ip = CharField(default='0.0.0.0')
    database_host = CharField(default='')
    database_port = IntegerField(null=True)
    sqlite_path = CharField(max_length=500, default='')
    revision = IntegerField(default=1)
    applied_revision = IntegerField(default=0)
    applied_roles = JSONField(default=list)
    image = CharField(default='')
    checked_at = DateTimeField(null=True)
    state = CharField(default='unknown')

    class Meta:
        table_name = 'result_servers'


class ResultServerEndpoint(ReceiverModel):
    server = ForeignKeyField(ResultServer, on_delete='CASCADE')
    endpoint = ForeignKeyField(ReceiverEndpoint, on_delete='RESTRICT')

    class Meta:
        table_name = 'result_server_endpoints'
        indexes = ((('server', 'endpoint'), True),)


class AgentRouting(ReceiverModel):
    agent = ForeignKeyField(SmonAgent, unique=True, on_delete='CASCADE')
    inherit = BooleanField(default=True)
    policy = CharField(max_length=16, default='balance')
    applied_hash = CharField(max_length=64, null=True)
    applied_at = DateTimeField(null=True)

    class Meta:
        table_name = 'agent_routing'


class AgentReceiver(ReceiverModel):
    agent = ForeignKeyField(SmonAgent, on_delete='CASCADE')
    endpoint = ForeignKeyField(ReceiverEndpoint, on_delete='RESTRICT')
    position = IntegerField(default=0)

    class Meta:
        table_name = 'agent_receivers'
        indexes = ((('agent', 'endpoint'), True),)


class GroupReceiver(ReceiverModel):
    group = ForeignKeyField(Groups, on_delete='CASCADE')
    endpoint = ForeignKeyField(ReceiverEndpoint, on_delete='RESTRICT')
    position = IntegerField(default=0)

    class Meta:
        table_name = 'group_receivers'
        indexes = ((('group', 'endpoint'), True),)


class AppliedAgentReceiver(ReceiverModel):
    agent = ForeignKeyField(SmonAgent, on_delete='CASCADE')
    endpoint = ForeignKeyField(ReceiverEndpoint, on_delete='RESTRICT')

    class Meta:
        table_name = 'applied_agent_receivers'
        indexes = ((('agent', 'endpoint'), True),)


class PendingAgentReceiver(ReceiverModel):
    task = ForeignKeyField(InstallationTasks, on_delete='CASCADE')
    agent = ForeignKeyField(SmonAgent, on_delete='CASCADE')
    endpoint = ForeignKeyField(ReceiverEndpoint, on_delete='RESTRICT')

    class Meta:
        table_name = 'pending_agent_receivers'
        indexes = ((('task', 'endpoint'), True),)


class ProjectReceiver(ReceiverModel):
    project = ForeignKeyField(ClientProject, unique=True, on_delete='CASCADE')
    endpoint = ForeignKeyField(ReceiverEndpoint, on_delete='RESTRICT')

    class Meta:
        table_name = 'project_receivers'


RECEIVER_TABLES = [ReceiverEndpoint, ResultServer, ResultServerEndpoint, AgentRouting,
                   AgentReceiver, GroupReceiver, ProjectReceiver, AppliedAgentReceiver, PendingAgentReceiver]
