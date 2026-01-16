from peewee import DateTimeField, AutoField, CharField, ForeignKeyField, IntegerField, SQL, Model, TextField, \
    BooleanField, FloatField, MySQLDatabase, ModelSelect
from playhouse.migrate import *
from datetime import datetime
from playhouse.shortcuts import ReconnectMixin
from playhouse.sqlite_ext import SqliteExtDatabase
from playhouse.pool import PooledPostgresqlExtDatabase
from psycopg2 import InterfaceError, OperationalError

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


class SafePooledPostgresqlExtDatabase(PooledPostgresqlExtDatabase):
    def execute_sql(self, sql, params=None, commit=True, **kwargs):
        try:
            return super().execute_sql(sql, params=params, commit=commit, **kwargs)
        except (InterfaceError, OperationalError):
            try:
                self.close()
            except Exception:
                pass
            self.connect(reuse_if_open=True)
            return super().execute_sql(sql, params=params, commit=commit, **kwargs)


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
        conn = SafePooledPostgresqlExtDatabase(db, **kwargs)
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


conn = connect()


class AutoReconnectSelect(ModelSelect):
    def execute(self, database=None):
        db = database or self.model._meta.database
        if db.is_closed():
            db.connect()
        return super().execute(database)


class BaseModel(Model):
    class Meta:
        database = conn

    @classmethod
    def select(cls, *fields):
        if not fields:
            fields = cls._meta.sorted_fields
        return AutoReconnectSelect(cls, fields)


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


class Migration(BaseModel):
    id = AutoField()
    name = CharField(unique=True)
    applied_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'migrations'


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
    server_id = ForeignKeyField(Server, on_delete='RESTRICT', index=True)
    name = CharField()
    uuid = CharField(index=True)
    enabled = IntegerField(constraints=[SQL('DEFAULT 1')])
    description = CharField()
    shared = IntegerField(constraints=[SQL('DEFAULT 0')], index=True)
    port = IntegerField(constraints=[SQL('DEFAULT 5701')])
    region_id = ForeignKeyField(Region, null=True, on_delete='SET NULL', index=True)

    class Meta:
        table_name = 'smon_agents'


class MultiCheck(BaseModel):
    id = AutoField
    entity_type = CharField()
    group_id = ForeignKeyField(Groups, on_delete='RESTRICT')
    check_group_id = ForeignKeyField(SmonGroup, null=True, on_delete='SET NULL')
    runbook = TextField(null=True)
    priority = CharField(constraints=[SQL("DEFAULT 'critical'")])
    expiration = DateTimeField(null=True)
    threshold_timeout = IntegerField(default=0)
    name = CharField(null=True)
    description = CharField(null=True)

    class Meta:
        table_name = 'multi_check'


class SMON(BaseModel):
    id = AutoField()
    status = IntegerField(constraints=[SQL('DEFAULT 1')])
    enabled = IntegerField(constraints=[SQL('DEFAULT 1')])
    response_time = CharField(null=True)
    time_state = DateTimeField(default=datetime.now)
    telegram_channel_id = IntegerField(null=True)
    group_id = IntegerField(index=True)
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
    region_id = ForeignKeyField(Region, null=True, on_delete='SET NULL', index=True)
    country_id = ForeignKeyField(Country, null=True, on_delete='SET NULL', index=True)
    agent_id = ForeignKeyField(SmonAgent, null=True, on_delete='RESTRICT', index=True)
    multi_check_id = ForeignKeyField(MultiCheck, null=True, on_delete='CASCADE', index=True)
    retries = IntegerField(constraints=[SQL('DEFAULT 3')])
    current_retries = IntegerField(constraints=[SQL('DEFAULT 0')])

    class Meta:
        table_name = 'smon'
        indexes = (
            # Composite index for group_id and multi_check_id which are often queried together
            (('group_id', 'multi_check_id'), False),
        )


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
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', index=True)
    check_id = IntegerField(index=True)
    response_time = FloatField()
    status = IntegerField(index=True)
    mes = CharField()
    date = DateTimeField(default=datetime.now, index=True)
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
        indexes = (
            # Composite index for smon_id and check_id which are often queried together
            (('smon_id', 'check_id'), False),
            # Composite index for smon_id and date which are often used for sorting and filtering
            (('smon_id', 'date'), False),
        )


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
    accepted_status_codes = JSONField(null=True)
    body = CharField(null=True)
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])
    headers = JSONField(null=True)
    body_req = JSONField(null=True)
    ignore_ssl_error = IntegerField(constraints=[SQL('DEFAULT 0')])
    redirects = IntegerField(constraints=[SQL('DEFAULT 10')])
    auth = JSONField(null=True)
    body_json = JSONField(null=True)
    proxy = JSONField(null=True)
    headers_response = JSONField(null=True)

    class Meta:
        table_name = 'smon_http_check'
        primary_key = False


class SmonPingCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    ip = CharField()
    packet_size = IntegerField(constraints=[SQL('DEFAULT 56')])
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])
    count_packets = IntegerField(default=4)

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
    multi_check_id = ForeignKeyField(MultiCheck, on_delete='Cascade')

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


class InstallationTasks(BaseModel):
    id = AutoField
    service_name = CharField()
    status = CharField(default='created')
    action = CharField(null=True)
    error = CharField(null=True)
    start_date = DateTimeField(default=datetime.now)
    finish_date = DateTimeField(default=datetime.now)
    group_id = ForeignKeyField(Groups, null=True, on_delete='SET NULL')
    user_id = ForeignKeyField(User, null=True, on_delete='SET NULL')
    server_id = ForeignKeyField(Server, null=True, on_delete='SET NULL')

    class Meta:
        table_name = 'installation_tasks'


class AlertState(BaseModel):
    multi_check_id = ForeignKeyField(MultiCheck, on_delete='CASCADE', backref='state', index=True)
    alert_key = CharField(default='', index=True)
    active = BooleanField(default=False)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'alert_state'
        indexes = (
            (('multi_check_id', 'alert_key'), True),
        )


class AlertEvent(BaseModel):
    multi_check_id = ForeignKeyField(MultiCheck, on_delete='CASCADE', index=True)
    alert_key = CharField(default='', index=True)
    message = TextField()
    entity_name = CharField()
    level = CharField()
    kwargs = JSONField()
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'alert_event'


class AggregatorLock(BaseModel):
    lock_name = CharField(primary_key=True)
    owner = CharField()
    expires_at = DateTimeField()

    class Meta:
        table_name = 'aggregator_lock'


def create_tables():
    conn = connect()
    with conn:
        conn.create_tables(
            [Groups, User, Server, Role, Telegram, Slack, UserGroups, Setting, Cred, Version, ActionHistory, Region,
             SystemInfo, UserName, PD, SmonHistory, SmonAgent, SmonTcpCheck, SmonHttpCheck, SmonPingCheck, SmonDnsCheck, RoxyTool,
             SmonStatusPage, SmonStatusPageCheck, SMON, SmonGroup, MM, RMONAlertsHistory, SmonSMTPCheck, SmonRabbitCheck,
             Country, MultiCheck, Email, InstallationTasks, Migration, AlertEvent, AlertState, AggregatorLock]
        )
