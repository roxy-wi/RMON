from peewee import IntegrityError

from app.modules.db.db_model import Groups, Setting, UserGroups
from app.modules.db.common import out_error, resource_not_empty
from app.modules.roxywi.exception import RoxywiResourceNotFound


def select_groups(**kwargs):
	if kwargs.get("group") is not None:
		query = Groups.select().where(Groups.name == kwargs.get('group'))
	elif kwargs.get("id") is not None:
		query = Groups.select().where(Groups.group_id == kwargs.get('id'))
	else:
		query = Groups.select().order_by(Groups.group_id)

	try:
		query_res = query.execute()
	except Groups.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)
	else:
		return query_res


def add_group(name: str, description: str) -> int:
	try:
		last_insert = Groups.insert(name=name, description=description)
		last_insert_id = last_insert.execute()
	except Exception as e:
		out_error(e)
	else:
		add_setting_for_new_group(last_insert_id)
		return last_insert_id


def add_setting_for_new_group(group_id):
	group_id = str(group_id)
	data_source = [
		{'param': 'time_zone', 'value': 'UTC', 'section': 'main', 'desc': 'Time Zone', 'group_id': group_id},
		{'param': 'proxy', 'value': '', 'section': 'main', 'desc': 'IP address and port of the proxy server . Use proto://ip:port', 'group_id': group_id},
		{'param': 'session_ttl', 'value': '5', 'section': 'main', 'desc': 'TTL for a user session (in days)', 'group_id': group_id},
		{'param': 'token_ttl', 'value': '5', 'section': 'main', 'desc': 'TTL for a user token (in days)', 'group_id': group_id},
		{'param': 'tmp_config_path', 'value': '/tmp/', 'section': 'main', 'desc': 'Path to the temporary directory.', 'group_id': group_id},
		{'param': 'cert_path', 'value': '/etc/ssl/certs/', 'section': 'main', 'desc': 'Path to SSL dir', 'group_id': group_id},
		{'param': 'syslog_server_enable', 'value': '0', 'section': 'logs', 'desc': 'Enable getting logs from a syslog server; (0 - no, 1 - yes)', 'group_id': group_id},
		{'param': 'syslog_server', 'value': '', 'section': 'logs', 'desc': 'IP address of the syslog_server', 'group_id': group_id},
		{'param': 'ldap_enable', 'value': '0', 'section': 'ldap', 'desc': 'Enable LDAP', 'group_id': group_id},
		{'param': 'ldap_server', 'value': '', 'section': 'ldap', 'desc': 'IP address of the LDAP server', 'group_id': group_id},
		{'param': 'ldap_port', 'value': '389', 'section': 'ldap', 'desc': 'LDAP port (port 389 or 636 is used by default)', 'group_id': group_id},
		{'param': 'ldap_user', 'value': '', 'section': 'ldap', 'desc': 'LDAP username. Format: user@domain.com', 'group_id': group_id},
		{'param': 'ldap_password', 'value': '', 'section': 'ldap', 'desc': 'LDAP password', 'group_id': group_id},
		{'param': 'ldap_base', 'value': '', 'section': 'ldap', 'desc': 'Base domain. Example: dc=domain, dc=com', 'group_id': group_id},
		{'param': 'ldap_domain', 'value': '', 'section': 'ldap', 'desc': 'LDAP domain for logging in', 'group_id': group_id},
		{'param': 'ldap_class_search', 'value': 'user', 'section': 'ldap', 'desc': 'Class for searching the user', 'group_id': group_id},
		{'param': 'ldap_user_attribute', 'value': 'sAMAccountName', 'section': 'ldap', 'desc': 'Attribute to search users by', 'group_id': group_id},
		{'param': 'ldap_search_field', 'value': 'mail', 'section': 'ldap', 'desc': 'UserPost\'s email address', 'group_id': group_id},
		{'param': 'ldap_type', 'value': '0', 'section': 'ldap', 'desc': 'Use LDAPS', 'group_id': group_id},
	]

	try:
		Setting.insert_many(data_source).execute()
	except Exception as e:
		out_error(e)


def delete_group(group_id):
	try:
		Groups.delete().where(Groups.group_id == group_id).execute()
		UserGroups.delete().where(UserGroups.user_group_id == group_id).execute()
		delete_group_settings(group_id)
	except IntegrityError:
		resource_not_empty()
	except Exception as e:
		out_error(e)


def delete_group_settings(group_id):
	try:
		group_for_delete = Setting.delete().where(Setting.group_id == group_id)
		group_for_delete.execute()
	except Exception as e:
		out_error(e)


def update_group(name, descript, group_id):
	try:
		group_update = Groups.update(name=name, description=descript).where(Groups.group_id == group_id)
		group_update.execute()
	except Exception as e:
		out_error(e)
		return False
	else:
		return True


def get_group_name_by_id(group_id):
	try:
		group_name = Groups.get(Groups.group_id == group_id)
	except Groups.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)
	else:
		return group_name.name
