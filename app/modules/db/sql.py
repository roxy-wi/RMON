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

	if kwargs.get('group_id'):
		user_group_id = kwargs.get('group_id')

	if param in ('proxy', 'agent_port', 'master_port', 'master_ip', 'rmon_name', 'use_victoria_metrics', 'victoria_metrics_select'):
		user_group_id = 1

	if kwargs.get('all'):
		query = Setting.select().where(Setting.group_id == user_group_id).order_by(Setting.section.desc())
	elif kwargs.get('section'):
		query = Setting.select().where((Setting.group_id == user_group_id) & (Setting.section == kwargs.get('section')))
	else:
		query = Setting.select().where((Setting.param == param) & (Setting.group_id == user_group_id))

	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		if kwargs.get('all') or kwargs.get('section'):
			return query_res
		else:
			for setting in query_res:
				if param in (
					'session_ttl', 'token_ttl', 'ldap_type', 'ldap_port', 'ldap_enable', 'log_time_storage', 'syslog_server_enable',
					'keep_history_range', 'ssl_expire_warning_alert', 'ssl_expire_critical_alert', 'action_keep_history_range',
					'use_victoria_metrics', 'mail_enabled', 'mail_send_hello_message'
				):
					return int(setting.value)
				else:
					return setting.value


def update_setting(param: str, val: str, user_group: int) -> None:
	query = Setting.update(value=val).where((Setting.param == param) & (Setting.group_id == user_group))
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def select_roles():
	try:
		return Role.select().execute()
	except Exception as e:
		out_error(e)
