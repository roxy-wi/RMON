from flask_jwt_extended import get_jwt, verify_jwt_in_request

from app.modules.db.db_model import Setting, Role
from app.modules.db.common import out_error


def get_setting(param, **kwargs):
	try:
		verify_jwt_in_request()
		claims = get_jwt()
		user_group_id = claims['group']
	except Exception:
		user_group_id = 1

	if param in ('proxy', 'agent_port', 'master_port', 'master_ip'):
		user_group_id = 1

	if kwargs.get('all'):
		query = Setting.select().where(Setting.group == user_group_id).order_by(Setting.section.desc())
	else:
		query = Setting.select().where((Setting.param == param) & (Setting.group == user_group_id))

	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		if kwargs.get('all'):
			return query_res
		else:
			for setting in query_res:
				if param in (
					'session_ttl', 'token_ttl', 'ldap_type', 'ldap_port', 'ldap_enable', 'log_time_storage', 'syslog_server_enable',
					'keep_history_range', 'ssl_expire_warning_alert', 'ssl_expire_critical_alert', 'action_keep_history_range'
				):
					return int(setting.value)
				else:
					return setting.value


def update_setting(param: str, val: str, user_group: int) -> bool:
	query = Setting.update(value=val).where((Setting.param == param) & (Setting.group == user_group))
	try:
		query.execute()
		return True
	except Exception as e:
		out_error(e)
		return False


def select_roles():
	query = Role.select()
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		return query_res
