from playhouse.migrate import *
from datetime import datetime
from playhouse.shortcuts import ReconnectMixin
from playhouse.sqlite_ext import SqliteExtDatabase

import app.modules.roxy_wi_tools as roxy_wi_tools

get_config = roxy_wi_tools.GetConfigVar()
mysql_enable = get_config.get_config_var('mysql', 'enable')


class ReconnectMySQLDatabase(ReconnectMixin, MySQLDatabase):
    pass


def connect(get_migrator=None):
    if mysql_enable == '1':
        mysql_user = get_config.get_config_var('mysql', 'mysql_user')
        mysql_password = get_config.get_config_var('mysql', 'mysql_password')
        mysql_db = get_config.get_config_var('mysql', 'mysql_db')
        mysql_host = get_config.get_config_var('mysql', 'mysql_host')
        mysql_port = get_config.get_config_var('mysql', 'mysql_port')
        conn = ReconnectMySQLDatabase(mysql_db, user=mysql_user, password=mysql_password, host=mysql_host, port=int(mysql_port))
        migrator = MySQLMigrator(conn)
    else:
        db = "/var/lib/rmon/rmon.db"
        conn = SqliteExtDatabase(db, pragmas=(
                ('cache_size', -1024 * 64),  # 64MB page-cache.
                ('journal_mode', 'wal'),  # Use WAL-mode (you should always use this!).
                ('foreign_keys', 1)
            ))
        migrator = SqliteMigrator(conn)
    if get_migrator:
        return migrator
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
    ldap_user = IntegerField(constraints=[SQL('DEFAULT "0"')])
    enabled = IntegerField(constraints=[SQL('DEFAULT "1"')])
    user_services = CharField(constraints=[SQL('DEFAULT "1 2 3 4 5"')])
    last_login_date = DateTimeField(constraints=[SQL('DEFAULT "0000-00-00 00:00:00"')])
    last_login_ip = CharField(null=True)

    class Meta:
        table_name = 'user'


class Server(BaseModel):
    server_id = AutoField(column_name='id')
    hostname = CharField()
    ip = CharField(constraints=[SQL('UNIQUE')])
    groups = CharField()
    enable = IntegerField(constraints=[SQL('DEFAULT 1')])
    cred = IntegerField(constraints=[SQL('DEFAULT 1')])
    alert = IntegerField(constraints=[SQL('DEFAULT 0')])
    port = IntegerField(constraints=[SQL('DEFAULT 22')])
    desc = CharField(null=True)
    pos = IntegerField(constraints=[SQL('DEFAULT 0')])

    class Meta:
        table_name = 'servers'


class Role(BaseModel):
    role_id = AutoField(column_name='id')
    name = CharField(constraints=[SQL('UNIQUE')])
    description = CharField()

    class Meta:
        table_name = 'role'


class Telegram(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    groups = IntegerField()

    class Meta:
        table_name = 'telegram'


class Slack(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    groups = IntegerField()

    class Meta:
        table_name = 'slack'


class MM(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    groups = IntegerField()

    class Meta:
        table_name = 'mattermost'


class PD(BaseModel):
    id = AutoField()
    token = CharField()
    chanel_name = CharField()
    groups = IntegerField()

    class Meta:
        table_name = 'pd'


class UUID(BaseModel):
    user_id = ForeignKeyField(User, on_delete='Cascade')
    uuid = CharField()
    exp = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'uuid'
        primary_key = False


class Setting(BaseModel):
    param = CharField()
    value = CharField(null=True)
    section = CharField()
    desc = CharField()
    group = IntegerField(null=True, constraints=[SQL('DEFAULT 1')])

    class Meta:
        table_name = 'settings'
        primary_key = False
        constraints = [SQL('UNIQUE (param, `group`)')]


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

    class Meta:
        table_name = 'cred'
        constraints = [SQL('UNIQUE (name, `group_id`)')]


class Version(BaseModel):
    version = CharField()

    class Meta:
        table_name = 'version'
        primary_key = False


class SmonGroup(BaseModel):
    id = AutoField()
    name = CharField()
    user_group = IntegerField(constraints=[SQL('DEFAULT 1')])

    class Meta:
        table_name = 'smon_groups'
        constraints = [SQL('UNIQUE (name, user_group)')]


class SMON(BaseModel):
    id = AutoField()
    name = CharField(null=True)
    port = IntegerField(null=True)
    status = IntegerField(constraints=[SQL('DEFAULT 1')])
    en = IntegerField(constraints=[SQL('DEFAULT 1')])
    desc = CharField(null=True)
    response_time = CharField(null=True)
    time_state = DateTimeField(constraints=[SQL('DEFAULT "0000-00-00 00:00:00"')])
    group_id = IntegerField(null=True)
    http = CharField(null=True)
    body_status = IntegerField(constraints=[SQL('DEFAULT 1')])
    telegram_channel_id = IntegerField(null=True)
    user_group = IntegerField()
    slack_channel_id = IntegerField(null=True)
    ssl_expire_warning_alert = IntegerField(constraints=[SQL('DEFAULT 0')])
    ssl_expire_critical_alert = IntegerField(constraints=[SQL('DEFAULT 0')])
    ssl_expire_date = CharField(null=True)
    pd_channel_id = IntegerField(null=True)
    mm_channel_id = IntegerField(null=True)
    check_type = CharField(constraints=[SQL('DEFAULT "tcp"')])
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    check_timeout = IntegerField(constraints=[SQL('DEFAULT 2')])

    class Meta:
        table_name = 'smon'
        constraints = [SQL('UNIQUE (name, port)')]


class Alerts(BaseModel):
    message = CharField()
    level = CharField()
    ip = CharField()
    port = IntegerField()
    user_group = IntegerField(constraints=[SQL('DEFAULT 1')])
    service = CharField()
    date = DateTimeField(default=datetime.now)

    class Meta:
        table_name = 'alerts'
        primary_key = False


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


class SmonAgent(BaseModel):
    id = AutoField()
    server_id = ForeignKeyField(Server, on_delete='Cascade')
    name = CharField()
    uuid = CharField()
    enabled = IntegerField(constraints=[SQL('DEFAULT 1')])
    desc = CharField()
    shared = IntegerField(constraints=[SQL('DEFAULT 0')])
    port = IntegerField(constraints=[SQL('DEFAULT 5701')])

    class Meta:
        table_name = 'smon_agents'


class SmonTcpCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    ip = CharField()
    port = IntegerField()
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])
    agent_id = IntegerField(constraints=[SQL('DEFAULT 1')])

    class Meta:
        table_name = 'smon_tcp_check'
        primary_key = False


class SmonHttpCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    url = CharField()
    method = CharField(constraints=[SQL('DEFAULT "get"')])
    accepted_status_codes = CharField(constraints=[SQL('DEFAULT "200"')])
    body = CharField(null=True)
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])
    agent_id = IntegerField(constraints=[SQL('DEFAULT 1')])
    headers = CharField(null=True)
    body_req = CharField(null=True)

    class Meta:
        table_name = 'smon_http_check'
        primary_key = False


class SmonPingCheck(BaseModel):
    smon_id = ForeignKeyField(SMON, on_delete='Cascade', unique=True)
    ip = CharField()
    packet_size = IntegerField(constraints=[SQL('DEFAULT 56')])
    interval = IntegerField(constraints=[SQL('DEFAULT 120')])
    agent_id = IntegerField(constraints=[SQL('DEFAULT 1')])

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
    agent_id = IntegerField(constraints=[SQL('DEFAULT 1')])

    class Meta:
        table_name = 'smon_dns_check'
        primary_key = False


class SmonStatusPage(BaseModel):
    id = AutoField()
    name = CharField()
    slug = CharField(unique=True)
    desc = CharField(null=True)
    group_id = IntegerField()
    style = TextField(null=True)

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
            [Groups, User, Server, Role, Telegram, Slack, UUID, UserGroups, Setting, Cred, Version, ActionHistory,
             SystemInfo, UserName, PD, SmonHistory, SmonAgent, SmonTcpCheck, SmonHttpCheck, SmonPingCheck, SmonDnsCheck, RoxyTool,
             SmonStatusPage, SmonStatusPageCheck, SMON, Alerts, SmonGroup, MM]
        )
