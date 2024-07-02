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
		{'param': 'time_zone', 'value': 'UTC', 'section': 'main', 'desc': 'Time Zone', 'group': '1'},
		{'param': 'license', 'value': '', 'section': 'main', 'desc': 'License key', 'group': '1'},
		{'param': 'proxy', 'value': '', 'section': 'main', 'desc': 'IP address and port of the proxy server. Use proto://ip:port', 'group': '1'},
		{'param': 'session_ttl', 'value': '5', 'section': 'main', 'desc': 'TTL for a user session (in days)', 'group': '1'},
		{'param': 'token_ttl', 'value': '5', 'section': 'main', 'desc': 'TTL for a user token (in days)', 'group': '1'},
		{'param': 'tmp_config_path', 'value': '/tmp/', 'section': 'main',
			'desc': 'Path to the temporary directory. A valid path should be specified as the value of this parameter. '
					'The directory must be owned by the user specified in SSH settings', 'group': '1'},
		{'param': 'cert_path', 'value': '/etc/ssl/certs/', 'section': 'main',
			'desc': 'Path to SSL dir. Folder owner must be a user which set in the SSH settings. Path must exist', 'group': '1'},
		{'param': 'ldap_enable', 'value': '0', 'section': 'ldap', 'desc': 'Enable LDAP', 'group': '1'},
		{'param': 'ldap_server', 'value': '', 'section': 'ldap', 'desc': 'IP address of the LDAP server', 'group': '1'},
		{'param': 'ldap_port', 'value': '389', 'section': 'ldap', 'desc': 'LDAP port (port 389 or 636 is used by default)', 'group': '1'},
		{'param': 'ldap_user', 'value': '', 'section': 'ldap', 'desc': 'LDAP username. Format: user@domain.com', 'group': '1'},
		{'param': 'ldap_password', 'value': '', 'section': 'ldap', 'desc': 'LDAP password', 'group': '1'},
		{'param': 'ldap_base', 'value': '', 'section': 'ldap', 'desc': 'Base domain. Example: dc=domain, dc=com', 'group': '1'},
		{'param': 'ldap_domain', 'value': '', 'section': 'ldap', 'desc': 'LDAP domain for logging in', 'group': '1'},
		{'param': 'ldap_class_search', 'value': 'user', 'section': 'ldap', 'desc': 'Class for searching the user', 'group': '1'},
		{'param': 'ldap_user_attribute', 'value': 'userPrincipalName', 'section': 'ldap', 'desc': 'Attribute to search users by', 'group': '1'},
		{'param': 'ldap_search_field', 'value': 'mail', 'section': 'ldap', 'desc': 'UserPost\'s email address', 'group': '1'},
		{'param': 'ldap_type', 'value': '0', 'section': 'ldap', 'desc': 'Use LDAPS', 'group': '1'},
		{'param': 'keep_history_range', 'value': '14', 'section': 'smon', 'desc': 'Retention period for RMON history', 'group': '1'},
		{'param': 'action_keep_history_range', 'value': '30', 'section': 'monitoring', 'desc': 'Retention period for Action history', 'group': '1'},
		{'param': 'ssl_expire_warning_alert', 'value': '14', 'section': 'smon', 'desc': 'Warning alert about a SSL certificate expiration (in days)', 'group': '1'},
		{'param': 'ssl_expire_critical_alert', 'value': '7', 'section': 'smon', 'desc': 'Critical alert about a SSL certificate expiration (in days)', 'group': '1'},
		{'param': 'master_ip', 'value': '', 'section': 'smon', 'desc': '', 'group': '1'},
		{'param': 'master_port', 'value': '5100', 'section': 'smon', 'desc': '', 'group': '1'},
		{'param': 'rabbitmq_host', 'value': '127.0.0.1', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server host', 'group': '1'},
		{'param': 'rabbitmq_port', 'value': '5672', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server port', 'group': '1'},
		{'param': 'rabbitmq_port', 'value': '5672', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server port', 'group': '1'},
		{'param': 'rabbitmq_vhost', 'value': '/', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server vhost', 'group': '1'},
		{'param': 'rabbitmq_queue', 'value': 'roxy-wi', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server queue', 'group': '1'},
		{'param': 'rabbitmq_user', 'value': 'roxy-wi', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server user', 'group': '1'},
		{'param': 'rabbitmq_password', 'value': 'roxy-wi123', 'section': 'rabbitmq', 'desc': 'RabbitMQ-server user password', 'group': '1'},
		{'param': 'mail_ssl', 'value': '0', 'section': 'mail', 'desc': 'Enable TLS', 'group': '1'},
		{'param': 'mail_from', 'value': '', 'section': 'mail', 'desc': 'Address of sender', 'group': '1'},
		{'param': 'mail_smtp_host', 'value': '', 'section': 'mail', 'desc': 'SMTP server address', 'group': '1'},
		{'param': 'mail_smtp_port', 'value': '25', 'section': 'mail', 'desc': 'SMTP server port', 'group': '1'},
		{'param': 'mail_smtp_user', 'value': '', 'section': 'mail', 'desc': 'UserPost for auth', 'group': '1'},
		{'param': 'mail_smtp_password', 'value': '', 'section': 'mail', 'desc': 'Password for auth', 'group': '1'},
		{'param': 'log_time_storage', 'value': '14', 'section': 'logs', 'desc': 'Retention period for user activity logs (in days)', 'group': '1'},
		{'param': 'apache_log_path', 'value': f'/var/log/{apache_dir}/', 'section': 'logs', 'desc': 'Path to Apache logs. Apache service for RMON', 'group': '1'},
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
		{'name': 'admin', 'description': 'Has access everywhere except the Admin area'},
		{'name': 'user', 'description': 'Has the same rights as the admin but has no access to the Servers page'},
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
		if e.args[0] == 'duplicate column name: check_timeout' or str(e) == '(1060, "Duplicate column name \'check_timeout\'")':
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
		if e.args[0] == 'duplicate column name: port' or str(e) == '(1060, "Duplicate column name \'port\'")':
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
			migrator.rename_column('user', 'activeuser', 'enabled'),
			migrator.rename_column('user', 'groups', 'group_id'),
			migrator.rename_column('cred', 'enable', 'key_enabled'),
			migrator.rename_column('cred', 'groups', 'group_id'),
		)
	except Exception as e:
		if e.args[0] == 'no such column: "activeuser"' or str(e) == '(1060, no such column: "activeuser")':
			print("Updating... DB has been updated to version 1.1")
		elif e.args[0] == "'bool' object has no attribute 'sql'":
			print("Updating... DB has been updated to version 1.1")
		else:
			print("An error occurred:", e)


def update_ver():
	try:
		Version.update(version='1.1.0').execute()
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


if __name__ == "__main__":
	create_tables()
	default_values()
	update_all()
