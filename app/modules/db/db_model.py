from playhouse.migrate import *
from datetime import datetime
from playhouse.shortcuts import ReconnectMixin
from playhouse.sqlite_ext import SqliteExtDatabase
from playhouse.pool import PooledPostgresqlExtDatabase

import app.modules.roxy_wi_tools as roxy_wi_tools

get_config = roxy_wi_tools.GetConfigVar()
pgsql_enable = get_config.get_config_var('pgsql', 'enable')
mysql_enable = get_config.get_config_var('mysql', 'enable')

if pgsql_enable == '1':
    from playhouse.postgres_ext import BinaryJSONField as JSONField
elif mysql_enable == '1':
    from playhouse.mysql_ext import JSONField
else:
    from playhouse.sqlite_ext import JSONField


class ReconnectMySQLDatabase(ReconnectMixin, MySQLDatabase):
    pass


def connect(get_migrator=None):
    if pgsql_enable == '1':
        db = get_config.get_config_var('pgsql', 'db')
        kwargs = {
            "user": get_config.get_config_var('pgsql', 'user'),
            "password": get_config.get_config_var('pgsql', 'password'),
            "host": get_config.get_config_var('pgsql', 'host'),
            "port": int(get_config.get_config_var('pgsql', 'port')),
            "max_connections": 32,
            "stale_timeout": 300
        }
        conn = PooledPostgresqlExtDatabase(db, **kwargs)
        migration = PostgresqlMigrator(conn)
    elif mysql_enable == '1':
        mysql_db = get_config.get_config_var('mysql', 'mysql_db')
        kwargs = {
            "user": get_config.get_config_var('mysql', 'mysql_user'),
            "password": get_config.get_config_var('mysql', 'mysql_password'),
            "host": get_config.get_config_var('mysql', 'mysql_host'),
            "port": int(get_config.get_config_var('mysql', 'mysql_port'))
        }
        conn = ReconnectMySQLDatabase(mysql_db, **kwargs)
        migration = MySQLMigrator(conn)
    else:
        db = "/var/lib/rmon/rmon.db"
        conn = SqliteExtDatabase(db, pragmas=(
                ('cache_size', -1024 * 64),  # 64MB page-cache.
                ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
                ('foreign_keys', 1)
            ))
        migration = SqliteMigrator(conn)
    if get_migrator:
        return migration
    else:
        return conn


class BaseModel(Model):
    class Meta:
        database = connect()


class Groups(BaseModel):
    group_id = AutoField(column_name='id')
    name = CharField(constraints=[SQL('UNIQUE')])
    description = CharField(null=True)

    class Meta:
        table_name = 'groups'


class User(BaseModel):
    user_id = AutoField(column_name='id')
    username = CharField(constraints=[SQL('UNIQUE')])
    email = CharField(constraints=[SQL('UNIQUE')])
    password = CharField(null=True)
    role = CharField()
    group_id = ForeignKeyField(Groups, on_delete='Cascade')
    ldap_user = IntegerField(constraints=[SQL("DEFAULT '0'")])
    enabled = IntegerField(constraints=[SQL("DEFAULT '1'")])
    user_services = CharField(constraints=[SQL("DEFAULT '1 2 3 4 5'")])
    last_login_date = DateTimeField(null=True)
    last_login_ip = CharField(null=True)

    class Meta:
        table_name = 'user'


class Server(BaseModel):
    server_id = AutoField(column_name='id')
    hostname = CharField()
    ip = CharField(constraints=[SQL('UNIQUE')])
    group_id = CharField()
    enabled = IntegerField(constraints=[SQL('DEFAULT 1')])
    cred_id = IntegerField(constraints=[SQL('DEFAULT 1')])
    alert = IntegerField(constraints=[SQL('DEFAULT 0')])
    port = IntegerField(constraints=[SQL('DEFAULT 22')])
    description = CharField(null=True)
    pos = IntegerField(constraints=[SQL('DEFAULT 0')])

    class Meta:
        table_name = 'servers'


class Role(BaseModel):
    role_id = AutoField(column_name='id')
    name = CharField(constraints=[SQL('UNIQUE')])
    description = CharField()

    class Meta:
        table_name = 'role'


class Email(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    group_id = IntegerField()

    class Meta:
        table_name = 'emails'


class Telegram(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    group_id = IntegerField()

    class Meta:
        table_name = 'telegram'


class Slack(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    group_id = IntegerField()

    class Meta:
        table_name = 'slack'


class MM(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    group_id = IntegerField()

    class Meta:
        table_name = 'mattermost'


class PD(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    group_id = IntegerField()

    class Meta:
        table_name = 'pd'


class Setting(BaseModel):
    param = CharField()
    value = CharField(null=True)
    section = CharField()
    desc = CharField()
    group_id = IntegerField(null=True, constraints=[SQL('DEFAULT 1')])

    class Meta:
        table_name = 'settings'
        primary_key = False
        constraints = [SQL('UNIQUE (param, group_id)')]


class UserGroups(BaseModel):
    user_id = ForeignKeyField(User, on_delete='Cascade')
    user_group_id = ForeignKeyField(Groups, on_delete='Cascade')
    user_role_id = IntegerField()

    class Meta:
        table_name = 'user_groups'
        primary_key = False
        constraints = [SQL('UNIQUE (user_id, user_group_id)')]


class Cred(BaseModel):
    id = AutoField()
    name = CharField()
    key_enabled = IntegerField(constraints=[SQL('DEFAULT 1')])
    username = CharField()
    password = CharField(null=True)
    group_id = IntegerField(constraints=[SQL('DEFAULT 1')])
    passphrase = CharField(null=True)
    shared = IntegerField(constraints=[SQL('DEFAULT 0')])
    private_key = TextField(null=True)

    class Meta:
        table_name = 'cred'
        constraints = [SQL('UNIQUE (name, group_id)')]


class Version(BaseModel):
    version = CharField()

    class Meta:
        table_name = 'version'
        primary_key = False


class SmonGroup(BaseModel):
    id = AutoField()
    name = CharField()
    group_id = IntegerField(constraints=[SQL('DEFAULT 1')])

    class Meta:
        table_name = 'smon_groups'
        constraints = [SQL('UNIQUE (name, group_id)')]


class Country(BaseModel):
    id = AutoField()
    name = CharField()
    description = CharField()
    group_id = IntegerField(constraints=[SQL('DEFAULT 1')])
    enabled = BooleanField(default=True)
    shared = BooleanField(default=False)

    class Meta:
        table_name = 'countries'


class Region(BaseModel):
    id = AutoField()
    name = CharField()
    description = CharField()
    group_id = IntegerField(constraints=[SQL('DEFAULT 1')])
    enabled = BooleanField(default=True)
    shared = BooleanField(default=False)
    country_id = ForeignKeyField(Country, null=True, on_delete='SET NULL')

    class Meta:
        table_name = 'regions'


class SmonAgent(BaseModel):
    id = AutoField()
    server_id = ForeignKeyField(Server, on_delete='RESTRICT')
    name = CharField()
    uuid = CharField()
    enabled = IntegerField(constraints=[SQL('DEFAULT 1')])
    description = CharField()
    shared = IntegerField(constraints=[SQL('DEFAULT 0')])
    port = IntegerField(constraints=[SQL('DEFAULT 5701')])
    region_id = ForeignKeyField(Region, null=True, on_delete='SET NULL')

    class Meta:
        table_name = 'smon_agents'


class MultiCheck(BaseModel):
    id = AutoField
    entity_type = CharField()
    group_id = ForeignKeyField(Groups, on_delete='RESTRICT')
    check_group_id = ForeignKeyField(SmonGroup, null=True, on_delete='SET NULL')
    runbook = TextField(null=True)
    priority = CharField(constraints=[SQL("DEFAULT 'critical'")])

    class Meta:
        table_name = 'multi_check'


class SMON(BaseModel):
    id = AutoField()
    name = CharField(null=True)
    status = IntegerField(constraints=[SQL('DEFAULT 1')])
    enabled = IntegerField(constraints=[SQL('DEFAULT 1')])
    description = CharField(null=True)
    response_time = CharField(null=True)
    time_state = DateTimeField(default=datetime.now)
    body_status = IntegerField(constraints=[SQL('DEFAULT 1')])
    telegram_channel_id = IntegerField(null=True)
    group_id = IntegerField()
    slack_channel_id = IntegerField(null=True)
    ssl_expire_warning_alert = IntegerField(constraints=[SQL('DEFAULT 0')])
    ssl_expire_critical_alert = IntegerField(constraints=[SQL('DEFAULT 0')])
    ssl_expire_date = CharField(null=True)
    pd_channel_id = IntegerField(null=True)
    mm_channel_id = IntegerField(null=True)
    email_channel_id = IntegerField(null=True)
    check_type = CharField(constraints=[SQL("DEFAULT 'tcp'")])
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    check_timeout = IntegerField(constraints=[SQL('DEFAULT 2')])
    region_id = ForeignKeyField(Region, null=True, on_delete='SET NULL')
    country_id = ForeignKeyField(Country, null=True, on_delete='SET NULL')
    agent_id = ForeignKeyField(SmonAgent, null=True, on_delete='RESTRICT')
    multi_check_id = ForeignKeyField(MultiCheck, null=True, on_delete='CASCADE')
    retries = IntegerField(constraints=[SQL('DEFAULT 3')])
    current_retries = IntegerField(constraints=[SQL('DEFAULT 0')])

    class Meta:
        table_name = 'smon'


class RMONAlertsHistory(BaseModel):
    id = AutoField()
    name = CharField()
    message = CharField()
    level = CharField()
    rmon_id = ForeignKeyField(SMON, on_delete='Cascade')
    port = IntegerField()
    group_id = IntegerField(constraints=[SQL('DEFAULT 1')])
    service = CharField()
    date = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'rmon_alerts_history'


class ActionHistory(BaseModel):
    service = CharField(null=True)
    server_id = IntegerField(null=True)
    user_id = IntegerField(null=True)
    action = CharField(null=True)
    ip = CharField(null=True)
    date = DateTimeField(default=datetime.now)
    server_ip = CharField(null=True)
    hostname = CharField(null=True)

    class Meta:
        table_name = 'action_history'
        primary_key = False


class SystemInfo(BaseModel):
    id = AutoField()
    server_id = IntegerField()
    os_info = CharField()
    sys_info = CharField()
    cpu = CharField()
    ram = CharField()
    disks = CharField()
    network = TextField()

    class Meta:
        table_name = 'system_info'


class UserName(BaseModel):
    UserName = CharField(null=True)
    Status = IntegerField(constraints=[SQL('DEFAULT 0')])
    Plan = CharField(null=True)
    Method = CharField(null=True)

    class Meta:
        table_name = 'user_name'
        primary_key = False


class SmonHistory(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade')
    check_id = IntegerField()
    response_time = FloatField()
    status = IntegerField()
    mes = CharField()
    date = DateTimeField(default=datetime.now)
    name_lookup = CharField(null=True)
    connect = CharField(null=True)
    app_connect = CharField(null=True)
    pre_transfer = CharField(null=True)
    redirect = CharField(null=True)
    start_transfer = CharField(null=True)
    download = CharField(null=True)

    class Meta:
        table_name = 'smon_history'
        primary_key = False


class SmonTcpCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    ip = CharField()
    port = IntegerField()
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])

    class Meta:
        table_name = 'smon_tcp_check'
        primary_key = False


class SmonSMTPCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    ip = CharField()
    port = IntegerField()
    username = CharField()
    password = CharField()
    use_tls = IntegerField(constraints=[SQL('DEFAULT 1')])
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])
    ignore_ssl_error = IntegerField(constraints=[SQL('DEFAULT 0')])

    class Meta:
        table_name = 'smon_smtp_check'
        primary_key = False


class SmonRabbitCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    ip = CharField()
    port = IntegerField()
    username = CharField()
    password = CharField()
    use_tls = CharField(constraints=[SQL('DEFAULT 0')])
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])
    vhost = CharField(constraints=[SQL("DEFAULT '/'")])
    ignore_ssl_error = IntegerField(constraints=[SQL('DEFAULT 0')])

    class Meta:
        table_name = 'smon_rabbit_check'
        primary_key = False


class SmonHttpCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    url = CharField()
    method = CharField(constraints=[SQL("DEFAULT 'get'")])
    accepted_status_codes = CharField(constraints=[SQL("DEFAULT '200'")])
    body = CharField(null=True)
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])
    headers = JSONField(null=True)
    body_req = JSONField(null=True)
    ignore_ssl_error = IntegerField(constraints=[SQL('DEFAULT 0')])
    redirects = IntegerField(constraints=[SQL('DEFAULT 10')])

    class Meta:
        table_name = 'smon_http_check'
        primary_key = False


class SmonPingCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    ip = CharField()
    packet_size = IntegerField(constraints=[SQL('DEFAULT 56')])
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])

    class Meta:
        table_name = 'smon_ping_check'
        primary_key = False


class SmonDnsCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    ip = CharField()
    port = IntegerField(constraints=[SQL('DEFAULT 53')])
    resolver = CharField()
    record_type = CharField()
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])

    class Meta:
        table_name = 'smon_dns_check'
        primary_key = False


class SmonStatusPage(BaseModel):
    id = AutoField()
    name = CharField()
    slug = CharField(unique=True)
    description = CharField(null=True)
    group_id = IntegerField()
    custom_style = TextField(null=True)

    class Meta:
        table_name = 'smon_status_pages'


class SmonStatusPageCheck(BaseModel):
    page_id = ForeignKeyField(SmonStatusPage, on_delete='Cascade')
    check_id = ForeignKeyField(SMON, on_delete='Cascade')

    class Meta:
        table_name = 'smon_status_page_checks'
        primary_key = False


class RoxyTool(BaseModel):
    id = AutoField()
    name = CharField()
    current_version = CharField()
    new_version = CharField()
    is_roxy = IntegerField()
    desc = CharField()

    class Meta:
        table_name = 'roxy_tools'
        constraints = [SQL('UNIQUE (name)')]


def create_tables():
    conn = connect()
    with conn:
        conn.create_tables(
            [Groups, User, Server, Role, Telegram, Slack, UserGroups, Setting, Cred, Version, ActionHistory, Region,
             SystemInfo, UserName, PD, SmonHistory, SmonAgent, SmonTcpCheck, SmonHttpCheck, SmonPingCheck, SmonDnsCheck, RoxyTool,
             SmonStatusPage, SmonStatusPageCheck, SMON, SmonGroup, MM, RMONAlertsHistory, SmonSMTPCheck, SmonRabbitCheck,
             Country, MultiCheck, Email]
        )
