from app.modules.db.db_model import ActionHistory, RMONAlertsHistory, SMON
from app.modules.db.sql import get_setting
from app.modules.db.common import out_error
import app.modules.roxy_wi_tools as roxy_wi_tools
from app.modules.roxywi.exception import RoxywiResourceNotFound


def alerts_history(service, user_group, **kwargs):
	if kwargs.get('check_id'):
		query = RMONAlertsHistory.select().where(
			(RMONAlertsHistory.service == service) &
			(RMONAlertsHistory.rmon_id == kwargs.get('check_id')) &
			(RMONAlertsHistory.user_group == user_group)
		)
	else:
		query = RMONAlertsHistory.select().where(RMONAlertsHistory.service == service)
	try:
		return query.execute()
	except Exception as e:
		out_error(e)


def rmon_multi_check_history(multi_check_id: int, group_id: int):
	query = RMONAlertsHistory.select().join(SMON).where(
			(RMONAlertsHistory.service == 'RMON') &
			(RMONAlertsHistory.user_group == group_id) &
			(SMON.multi_check_id == multi_check_id)
	)
	try:
		return query.execute()
	except RMONAlertsHistory.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def insert_alerts(check_id, user_group, level, check_name, port, message, service):
	get_date = roxy_wi_tools.GetDate()
	cur_date = get_date.return_date('regular')
	try:
		RMONAlertsHistory.insert(
			user_group=user_group, message=message, level=level, port=port, service=service,
			date=cur_date, rmon_id=check_id, name=check_name
		).execute()
	except Exception as e:
		out_error(e)


def delete_alert_history(keep_interval: int, service: str):
	get_date = roxy_wi_tools.GetDate()
	cur_date = get_date.return_date('regular', timedelta_minus=keep_interval)
	query = RMONAlertsHistory.delete().where(
		(RMONAlertsHistory.date < cur_date) & (RMONAlertsHistory.service == service)
	)
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def insert_action_history(service: str, action: str, server_id: int, user_id: int, user_ip: str, server_ip: str, hostname: str):
	get_date = roxy_wi_tools.GetDate()
	cur_date = get_date.return_date('regular')
	try:
		ActionHistory.insert(
			service=service,
			action=action,
			server_id=server_id,
			user_id=user_id,
			ip=user_ip,
			date=cur_date,
			server_ip=server_ip,
			hostname=hostname
		).execute()
	except Exception as e:
		out_error(e)


def delete_action_history(server_id: int):
	query = ActionHistory.delete().where(ActionHistory.server_id == server_id)
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def delete_action_history_for_period():
	time_period = get_setting('action_keep_history_range')
	get_date = roxy_wi_tools.GetDate()
	cur_date = get_date.return_date('regular', timedelta_minus=time_period)
	query = ActionHistory.delete().where(ActionHistory.date < cur_date)
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def select_action_history_by_server_id(server_id: int):
	try:
		return ActionHistory.select().where(ActionHistory.server_id == server_id).execute()
	except Exception as e:
		out_error(e)


def select_action_history_by_user_id(user_id: int):
	try:
		return ActionHistory.select().where(ActionHistory.user_id == user_id).execute()
	except Exception as e:
		out_error(e)


def select_action_history_by_server_id_and_service(server_id: int, service: str):
	query = ActionHistory.select().where(
		(ActionHistory.server_id == server_id)
		& (ActionHistory.service == service)
	)
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		return query_res
