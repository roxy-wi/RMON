#!/usr/bin/env python3
import os
import sys
import distro

sys.path.append(os.path.join(sys.path[0], '/var/www/rmon/'))

from app.modules.db.db_model import *

migrator = connect(get_migrator=1)


def default_values():
	create_users = True
	if distro.id() == 'ubuntu':
		apache_dir = 'apache2'
	else:
		apache_dir = 'httpd'
	data_source = [
		{'param': 'time_zone', 'value': 'UTC', 'section': 'main', 'desc': 'Time Zone', 'group_id': '1'},
		{'param': 'license', 'value': '', 'section': 'main', 'desc': 'License key', 'group_id': '1'},
		{'param': 'proxy', 'value': '', 'section': 'main', 'desc': 'IP address and port of the proxy server. Use proto://ip:port', 'group_id': '1'},
		{'param': 'session_ttl', 'value': '5', 'section': 'main', 'desc': 'TTL for a user session (in days)', 'group_id': '1'},
		{'param': 'token_ttl', 'value': '5', 'section': 'main', 'desc': 'TTL for a user token (in days)', 'group_id': '1'},
		{'param': 'tmp_config_path', 'value': '/tmp/', 'section': 'main',
			'desc': 'Path to the temporary directory. A valid path should be specified as the value of this parameter. '
					'The directory must be owned by the user specified in SSH settings', 'group_id': '1'},
		{'param': 'cert_path', 'value': '/etc/ssl/certs/', 'section': 'main',
			'desc': 'Path to SSL dir. Folder owner must be a user which set in the SSH settings. Path must exist', 'group_id': '1'},
		{'param': 'ldap_enable', 'value': '0', 'section': 'ldap', 'desc': 'Enable LDAP', 'group_id': '1'},
		{'param': 'ldap_server', 'value': '', 'section': 'ldap', 'desc': 'IP address of the LDAP server', 'group_id': '1'},
		{'param': 'ldap_port', 'value': '389', 'section': 'ldap', 'desc': 'LDAP port (port 389 or 636 is used by default)', 'group_id': '1'},
		{'param': 'ldap_user', 'value': '', 'section': 'ldap', 'desc': 'LDAP username. Format: user@domain.com', 'group_id': '1'},
		{'param': 'ldap_password', 'value': '', 'section': 'ldap', 'desc': 'LDAP password', 'group_id': '1'},
		{'param': 'ldap_base', 'value': '', 'section': 'ldap', 'desc': 'Base domain. Example: dc=domain, dc=com', 'group_id': '1'},
		{'param': 'ldap_domain', 'value': '', 'section': 'ldap', 'desc': 'LDAP domain for logging in', 'group_id': '1'},
		{'param': 'ldap_class_search', 'value': 'user', 'section': 'ldap', 'desc': 'Class for searching the user', 'group_id': '1'},
		{'param': 'ldap_user_attribute', 'value': 'userPrincipalName', 'section': 'ldap', 'desc': 'Attribute to search users by', 'group_id': '1'},
		{'param': 'ldap_search_field', 'value': 'mail', 'section': 'ldap', 'desc': 'UserPost\'s email address', 'group_id': '1'},
		{'param': 'ldap_type', 'value': '0', 'section': 'ldap', 'desc': 'Use LDAPS', 'group_id': '1'},
		{'param': 'keep_history_range', 'value': '14', 'section': 'smon', 'desc': 'Retention period for RMON history', 'group_id': '1'},
		{'param': 'action_keep_history_range', 'value': '30', 'section': 'monitoring', 'desc': 'Retention period for Action history', 'group_id': '1'},
		{'param': 'ssl_expire_warning_alert', 'value': '14', 'section': 'smon', 'desc': 'Warning alert about a SSL certificate expiration (in days)', 'group_id': '1'},
		{'param': 'ssl_expire_critical_alert', 'value': '7', 'section': 'smon', 'desc': 'Critical alert about a SSL certificate expiration (in days)', 'group_id': '1'},
		{'param': 'master_ip', 'value': '', 'section': 'smon', 'desc': '', 'group_id': '1'},
		{'param': 'master_port', 'value': '5100', 'section': 'smon', 'desc': '', 'group_id': '1'},
		{'param': 'rabbitmq_host', 'value': '127.0.0.1', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server host', 'group_id': '1'},
		{'param': 'rabbitmq_port', 'value': '5672', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server port', 'group_id': '1'},
		{'param': 'rabbitmq_port', 'value': '5672', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server port', 'group_id': '1'},
		{'param': 'rabbitmq_vhost', 'value': '/', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server vhost', 'group_id': '1'},
		{'param': 'rabbitmq_queue', 'value': 'rmon', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server queue', 'group_id': '1'},
		{'param': 'rabbitmq_user', 'value': 'rmon', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server user', 'group_id': '1'},
		{'param': 'rabbitmq_password', 'value': 'rmon123', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server user password', 'group_id': '1'},
		{'param': 'mail_ssl', 'value': '0', 'section': 'mail', 'desc': 'Enable TLS', 'group_id': '1'},
		{'param': 'mail_from', 'value': '', 'section': 'mail', 'desc': 'Address of sender', 'group_id': '1'},
		{'param': 'mail_smtp_host', 'value': '', 'section': 'mail', 'desc': 'SMTP server address', 'group_id': '1'},
		{'param': 'mail_smtp_port', 'value': '25', 'section': 'mail', 'desc': 'SMTP server port', 'group_id': '1'},
		{'param': 'mail_smtp_user', 'value': '', 'section': 'mail', 'desc': 'UserPost for auth', 'group_id': '1'},
		{'param': 'mail_smtp_password', 'value': '', 'section': 'mail', 'desc': 'Password for auth', 'group_id': '1'},
		{'param': 'log_time_storage', 'value': '14', 'section': 'logs', 'desc': 'Retention period for user activity logs (in days)', 'group_id': '1'},
		{'param': 'apache_log_path', 'value': f'/var/log/{apache_dir}/', 'section': 'logs', 'desc': 'Path to Apache logs. Apache service for RMON', 'group_id': '1'},
	]

	try:
		Setting.insert_many(data_source).on_conflict_ignore().execute()
	except Exception as e:
		print(str(e))

	try:
		if Role.get(Role.name == 'superAdmin').role_id == 1:
			create_users = False
		else:
			create_users = True
	except Exception as e:
		print(str(e))

	try:
		Groups.insert(name='Default', description='All servers are included in this group by default', group_id=1).on_conflict_ignore().execute()
	except Exception as e:
		print(str(e))

	data_source = [
		{'username': 'admin', 'email': 'admin@localhost', 'password': '21232f297a57a5a743894a0e4a801fc3', 'role': '1', 'group_id': '1'},
		{'username': 'editor', 'email': 'editor@localhost', 'password': '5aee9dbd2a188839105073571bee1b1f', 'role': '2', 'group_id': '1'},
		{'username': 'guest', 'email': 'guest@localhost', 'password': '084e0343a0486ff05530df6c705c8bb4', 'role': '4', 'group_id': '1'}
	]

	try:
		if create_users:
			User.insert_many(data_source).on_conflict_ignore().execute()
	except Exception as e:
		print(str(e))

	data_source = [
		{'user_id': '1', 'user_group_id': '1', 'user_role_id': '1'},
		{'user_id': '2', 'user_group_id': '1', 'user_role_id': '2'},
		{'user_id': '3', 'user_group_id': '1', 'user_role_id': '4'}
	]

	try:
		if create_users:
			UserGroups.insert_many(data_source).on_conflict_ignore().execute()
	except Exception as e:
		print(str(e))

	data_source = [
		{'name': 'superAdmin', 'description': 'Has the highest level of administrative permissions and controls the actions of all other users'},
		{'name': 'admin', 'description': 'Has admin access to its groups'},
		{'name': 'user', 'description': 'Has the same rights as the admin but has no access to the Admin area'},
		{'name': 'guest', 'description': 'Read-only access'}
	]

	try:
		Role.insert_many(data_source).on_conflict_ignore().execute()
	except Exception as e:
		print(str(e))

	data_source = [
		{'name': 'rmon-socket', 'current_version': '1.0', 'new_version': '0', 'is_roxy': 1, 'desc': ''},
		{'name': 'rmon-server', 'current_version': '1.0', 'new_version': '0', 'is_roxy': 1, 'desc': ''},
		{'name': 'fail2ban', 'current_version': '1.0', 'new_version': '1.0', 'is_roxy': 0, 'desc': 'Fail2ban service'},
		{'name': 'rabbitmq-server', 'current_version': '1.0', 'new_version': '1.0', 'is_roxy': 0, 'desc': 'Rabbitmq service'},
	]

	try:
		RoxyTool.insert_many(data_source).on_conflict_ignore().execute()
	except Exception as e:
		print(str(e))

	if pgsql_enable:
		conn = connect()
		cursor = conn.cursor()
		try:
			sql = """SELECT setval('groups_id_seq', max(id)) FROM "groups";"""
			cursor.execute(sql)
		except Exception as e:
			print(e)


# Needs for an insert version in first time
def update_db_v_3_4_5_22():
	try:
		Version.insert(version='1.0').execute()
	except Exception as e:
		print('Cannot insert version %s' % e)


def update_db_v_1_0_4():
	try:
		migrate(
			migrator.add_column('smon', 'check_timeout', IntegerField(default=2)),
			migrator.add_column_default('smon', 'check_timeout', 2),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: check_timeout' or 'column "check_timeout" of relation "smon" already exists'
				or str(e) == '(1060, "Duplicate column name \'check_timeout\'")'):
			print('Updating... DB has been updated to version 1.0.4')
		else:
			print("An error occurred:", e)


def update_db_v_1_0_7():
	try:
		migrate(
			migrator.add_column('smon_agents', 'port', IntegerField(default=5101)),
			migrator.add_column_default('smon_agents', 'port', 5101),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: port' or 'column "port" of relation "smon_agents" already exists'
				or str(e) == '(1060, "Duplicate column name \'port\'")'):
			print('Updating... DB has been updated to version 1.0.7')
		else:
			print("An error occurred:", e)


def update_db_v_1_0_7_1():
	try:
		Setting.delete().where(Setting.param == 'agent_port').execute()
	except Exception as e:
		print("An error occurred:", e)
	else:
		print("Updating... DB has been updated to version 1.0.7-1")


def update_db_v_1_1():
	try:
		migrate(
			migrator.rename_column('smon_agents', 'desc', 'description'),
			migrator.rename_column('smon', 'desc', 'description'),
			migrator.rename_column('smon_status_pages', 'style', 'custom_style'),
			migrator.rename_column('smon_status_pages', 'desc', 'description'),
			migrator.rename_column('telegram', 'groups', 'group_id'),
			migrator.rename_column('slack', 'groups', 'group_id'),
			migrator.rename_column('mattermost', 'groups', 'group_id'),
			migrator.rename_column('pd', 'groups', 'group_id'),
			migrator.rename_column('smon', 'en', 'enabled'),
			migrator.rename_column('servers', 'groups', 'group_id'),
			migrator.rename_column('servers', 'cred', 'cred_id'),
			migrator.rename_column('servers', 'enable', 'enabled'),
			migrator.rename_column('user', 'activeuser', 'enabled'),
			migrator.rename_column('user', 'groups', 'group_id'),
			migrator.rename_column('cred', 'enable', 'key_enabled'),
			migrator.rename_column('cred', 'groups', 'group_id'),
		)
	except Exception as e:
		if e.args[0] == 'no such column: "desc"' or 'column "desc" does not exist' in str(e) or str(e) == '(1060, no such column: "desc")':
			print("Updating... DB has been updated to version 1.1")
		elif e.args[0] == "'bool' object has no attribute 'sql'":
			print("Updating... DB has been updated to version 1.1")
		else:
			print("An error occurred:", e)


def update_db_v_1_1_2():
	try:
		migrate(
			migrator.add_column('smon_smtp_check', 'ignore_ssl_error', IntegerField(default=0)),
			migrator.add_column_default('smon_smtp_check', 'ignore_ssl_error', 0),
			migrator.add_column('smon_http_check', 'ignore_ssl_error', IntegerField(default=0)),
			migrator.add_column_default('smon_http_check', 'ignore_ssl_error', 0),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: ignore_ssl_error' or 'column "ignore_ssl_error" of relation "smon" already exists'
				or str(e) == '(1060, "Duplicate column name \'ignore_ssl_error\'")'):
			print('Updating... DB has been updated to version 1.1.2')
		else:
			print("An error occurred:", e)


def update_db_v_1_1_3():
	try:
		migrate(
			migrator.rename_column('servers', 'creds_id', 'cred_id'),
			migrator.rename_column('servers', 'desc', 'description'),
		)
	except Exception as e:
		if e.args[0] == 'no such column: "creds_id"' or 'column "creds_id" does not exist' in str(e) or str(e) == '(1060, no such column: "creds_id")':
			print("Updating... DB has been updated to version 1.3")
		elif e.args[0] == "'bool' object has no attribute 'sql'":
			print("Updating... DB has been updated to version 1.3")
		else:
			print("An error occurred:", e)


def update_db_v_1_1_3_1():
	try:
		migrate(
			migrator.rename_column('smon_status_pages', 'desc', 'description')
		)
	except Exception as e:
		if e.args[0] == 'no such column: "desc"' or 'column "desc" does not exist' in str(e) or str(e) == '(1060, no such column: "desc")':
			print("Updating... DB has been updated to version 1.3")
		elif e.args[0] == "'bool' object has no attribute 'sql'":
			print("Updating... DB has been updated to version 1.3")
		else:
			print("An error occurred:", e)


def update_db_v_1_1_4():
	field = ForeignKeyField(Region, field=Region.id, null=True, on_delete='SET NULL')
	try:
		migrate(
			migrator.add_column('smon', 'region_id', field),
			migrator.add_column('smon_agents', 'region_id', field)
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: region_id' or 'column "region_id" of relation "smon" already exists'
				or str(e) == '(1060, "Duplicate column name \'region_id\'")'):
			print('Updating... DB has been updated to version 1.1.4')
		else:
			print("An error occurred:", e)


def update_db_v_1_1_4_1():
	try:
		if mysql_enable:
			migrate(
				migrator.add_column('cred', 'shared', IntegerField(default=0)),
			)
		else:
			migrate(
				migrator.add_column('cred', 'shared', IntegerField(constraints=[SQL('DEFAULT 0')])),
			)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: shared' or 'column "shared" of relation "cred" already exists'
				or str(e) == '(1060, "Duplicate column name \'shared\'")'):
			print('Updating... DB has been updated to version 1.1.4-1')
		else:
			print("An error occurred:", e)


def update_db_v_1_1_6():
	field = ForeignKeyField(Country, field=Country.id, null=True, on_delete='SET NULL')
	try:
		migrate(
			migrator.add_column('regions', 'country_id', field),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: country_id' or 'column "country_ud" of relation "smon" already exists'
				or str(e) == '(1060, "Duplicate column name \'country_id\'")'):
			print('Updating... DB has been updated to version 1.1.6')
		else:
			print("An error occurred:", e)


def update_db_v_1_2():
	field = ForeignKeyField(Country, field=Country.id, null=True, on_delete='SET NULL')
	try:
		migrate(
			migrator.add_column('smon', 'country_id', field),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: country_id' or 'column "country_id" of relation "smon" already exists'
				or str(e) == '(1060, "Duplicate column name \'country_id\'")'):
			print('Updating... DB has been updated to version 1.2')
		else:
			print("An error occurred:", e)


def update_db_v_1_2_1():
	field = ForeignKeyField(SmonAgent, field=SmonAgent.id, null=True, on_delete='RESTRICT')
	try:
		migrate(
			migrator.add_column('smon', 'agent_id', field),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: agent_id' or 'column "agent_id" of relation "smon" already exists'
				or str(e) == '(1060, "Duplicate column name \'agent_id\'")'):
			print('Updating... DB has been updated to version 1.2')
		else:
			print("An error occurred:", e)


def update_db_v_1_2_2():
	field = ForeignKeyField(MultiCheck, field=MultiCheck.id, null=True, on_delete='CASCADE')
	try:
		migrate(
			migrator.add_column('smon', 'multi_check_id', field),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: multi_check_id' or 'column "multi_check_id" of relation "smon" already exists'
				or str(e) == '(1060, "Duplicate column name \'multi_check_id\'")'):
			print('Updating... DB has been updated to version 1.2')
		else:
			print("An error occurred:", e)


def update_db_v_1_2_3():
	try:
		migrate(
			migrator.drop_column('smon_smtp_check', 'agent_id'),
			migrator.drop_column('smon_tcp_check', 'agent_id'),
			migrator.drop_column('smon_rabbit_check', 'agent_id'),
			migrator.drop_column('smon_ping_check', 'agent_id'),
			migrator.drop_column('smon_http_check', 'agent_id'),
			migrator.drop_column('smon_dns_check', 'agent_id'),
		)
	except Exception:
		pass


def update_db_v_1_2_4():
	try:
		migrate(
			migrator.rename_column('smon_groups', 'user_group', 'group_id'),
			migrator.rename_column('smon', 'group_id', 'check_group_id'),
			migrator.rename_column('smon', 'user_group', 'group_id')
		)
	except Exception as e:
		if e.args[0] == 'no such column: "user_group"' or 'column "user_group" does not exist' in str(e) or str(e) == '(1060, no such column: "user_group")':
			print("Updating... DB has been updated to version 1.2")
		elif e.args[0] == "'bool' object has no attribute 'sql'":
			print("Updating... DB has been updated to version 1.2")
		else:
			print("An error occurred:", e)


def update_db_v_1_2_5():
	try:
		migrate(
			migrator.drop_column('smon', 'check_group_id'),
		)
	except Exception:
		pass


def update_db_v_1_2_6():
	field = ForeignKeyField(SmonGroup, field=SmonGroup.id, null=True, on_delete='SET NULL')
	try:
		migrate(
			migrator.add_column('multi_check', 'check_group_id', field),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: check_group_id' or 'column "check_group_id" of relation "smon" already exists'
				or str(e) == '(1060, "Duplicate column name \'check_group_id\'")'):
			print('Updating... DB has been updated to version 1.2')
		else:
			print("An error occurred:", e)


def update_db_v_1_2_7():
	try:
		migrate(
			migrator.rename_column('settings', 'group', 'group_id'),
		)
	except Exception as e:
		if e.args[0] == 'no such column: "group"' or 'column "group" does not exist' in str(e) or str(e) == '(1060, no such column: "group")':
			print("Updating... DB has been updated to version 1.2")
		elif e.args[0] == "'bool' object has no attribute 'sql'":
			print("Updating... DB has been updated to version 1.2")
		else:
			print("An error occurred:", e)


def update_db_v_1_2_8():
	try:
		migrate(
			migrator.rename_column('rmon_alerts_history', 'user_group', 'group_id'),
		)
	except Exception as e:
		if e.args[0] == 'no such column: "user_group"' or 'column "user_group" does not exist' in str(e) or str(e) == '(1060, no such column: "user_group")':
			print("Updating... DB has been updated to version 1.2")
		elif e.args[0] == "'bool' object has no attribute 'sql'":
			print("Updating... DB has been updated to version 1.2")
		else:
			print("An error occurred:", e)


def update_db_v_1_3():
	try:
		migrate(
			migrator.add_column('cred', 'private_key', TextField(null=True)),
		)
	except Exception as e:
		if (e.args[0] == 'duplicate column name: private_key' or 'column "private_key" of relation "cred" already exists'
				or str(e) == '(1060, "Duplicate column name \'private_key\'")'):
			print('Updating... DB has been updated to version 1.3')
		else:
			print("An error occurred:", e)


def update_ver():
	try:
		Version.update(version='1.2.3.1').execute()
	except Exception:
		print('Cannot update version')


def check_ver():
	try:
		ver = Version.get()
	except Exception as e:
		print(str(e))
	else:
		return ver.version


def update_all():
	if check_ver() is None:
		update_db_v_3_4_5_22()
	update_ver()
	update_db_v_1_0_4()
	update_db_v_1_0_7()
	update_db_v_1_0_7_1()
	update_db_v_1_1()
	update_db_v_1_1_2()
	update_db_v_1_1_3()
	update_db_v_1_1_3_1()
	update_db_v_1_1_4()
	update_db_v_1_1_4_1()
	update_db_v_1_1_6()
	update_db_v_1_2()
	update_db_v_1_2_1()
	update_db_v_1_2_2()
	update_db_v_1_2_3()
	update_db_v_1_2_4()
	update_db_v_1_2_5()
	update_db_v_1_2_6()
	update_db_v_1_2_7()
	update_db_v_1_2_8()
	update_db_v_1_3()


if __name__ == "__main__":
	create_tables()
	default_values()
	update_all()
