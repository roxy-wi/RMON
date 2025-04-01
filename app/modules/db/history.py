from typing import Union

from app.modules.db.db_model import ActionHistory, RMONAlertsHistory, SMON, pgsql_enable
from app.modules.db.sql import get_setting
from app.modules.db.common import out_error
import app.modules.roxy_wi_tools as roxy_wi_tools
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.roxywi.class_models import HistoryQuery


def _return_sort_query(query: HistoryQuery) -> Union[str, None]:
	sort_query = None
	is_desc = False
	if query.sort_by:
		if query.sort_by.startswith('-'):
			is_desc = True
			query.sort_by = query.sort_by.replace('-', '')
		sorts = {
			'name': RMONAlertsHistory.name,
			'id': RMONAlertsHistory.id,
			'date': RMONAlertsHistory.date,
		}
		if is_desc:
			sort_query = sorts[query.sort_by].desc()
		else:
			sort_query = sorts[query.sort_by].asc()
	return sort_query


def alerts_history(service: str, group_id: int, query: HistoryQuery):
	where_query = (RMONAlertsHistory.service == service) & (RMONAlertsHistory.group_id == group_id)
	sort_query = _return_sort_query(query)
	# if pgsql_enable == '1':
	if sort_query:
		query = RMONAlertsHistory.select().where(where_query).order_by(sort_query).paginate(query.offset, query.limit)
	else:
		query = RMONAlertsHistory.select().where(where_query).paginate(query.offset, query.limit)

	try:
		return query.execute()
	except Exception as e:
		out_error(e)


def all_alerts_history(service: str, group_id: int, **kwargs):
	if kwargs.get('check_id'):
		query = RMONAlertsHistory.select().where(
			(RMONAlertsHistory.service == service) &
			(RMONAlertsHistory.rmon_id == kwargs.get('check_id')) &
			(RMONAlertsHistory.group_id == group_id)
		)
	else:
		query = RMONAlertsHistory.select().where(
			(RMONAlertsHistory.service == service) & (RMONAlertsHistory.group_id == group_id)
		)
	try:
		return query.execute()
	except Exception as e:
		out_error(e)


def total_alerts_history(service: str, group_id: int, **kwargs):
	if kwargs.get('check_id'):
		query = RMONAlertsHistory.select().where(
			(RMONAlertsHistory.service == service) &
			(RMONAlertsHistory.rmon_id == kwargs.get('check_id')) &
			(RMONAlertsHistory.group_id == group_id)
		).count()
	else:
		query = RMONAlertsHistory.select().where(
			(RMONAlertsHistory.service == service) & (RMONAlertsHistory.group_id == group_id)
		).count()
	try:
		return query
	except Exception as e:
		out_error(e)


def rmon_multi_check_history(multi_check_id: int, group_id: int, query: HistoryQuery):
	sort_query = _return_sort_query(query)
	where_query = (RMONAlertsHistory.service == 'RMON') & (RMONAlertsHistory.group_id == group_id) & (SMON.multi_check_id == multi_check_id)
	if sort_query:
		query = RMONAlertsHistory.select().join(SMON).where(where_query).order_by(sort_query).paginate(query.offset, query.limit)
	else:
		query = RMONAlertsHistory.select().join(SMON).where(where_query).paginate(query.offset, query.limit)
	try:
		return query.execute()
	except RMONAlertsHistory.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def all_rmon_multi_check_history(multi_check_id: int, group_id: int,):
	query = RMONAlertsHistory.select().join(SMON).where(
		(RMONAlertsHistory.service == 'RMON') &
		(RMONAlertsHistory.group_id == group_id) &
		(SMON.multi_check_id == multi_check_id)
	)
	try:
		return query.execute()
	except RMONAlertsHistory.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def total_rmon_multi_check_history(multi_check_id: int, group_id: int):
	query = RMONAlertsHistory.select().join(SMON).where(
		(RMONAlertsHistory.service == 'RMON') &
		(RMONAlertsHistory.group_id == group_id) &
		(SMON.multi_check_id == multi_check_id)
	).count()
	try:
		return query
	except RMONAlertsHistory.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def insert_alerts(check_id, group_id, level, check_name, port, message, service):
	get_date = roxy_wi_tools.GetDate()
	cur_date = get_date.return_date('regular')
	if port == '':
		port = 0
	try:
		RMONAlertsHistory.insert(
			group_id=group_id, message=message, level=level, port=port, service=service,
			date=cur_date, rmon_id=check_id, name=check_name
		).execute()
	except Exception as e:
		out_error(e)


def delete_alert_history(keep_interval: int, service: str):
	get_date = roxy_wi_tools.GetDate()
	cur_date = get_date.return_date('regular', timedelta_minus=keep_interval)
	try:
		RMONAlertsHistory.delete().where(
			(RMONAlertsHistory.date < cur_date) & (RMONAlertsHistory.service == service)
		).execute()
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
	try:
		ActionHistory.delete().where(ActionHistory.server_id == server_id).execute()
	except Exception as e:
		out_error(e)


def delete_action_history_for_period():
	time_period = get_setting('action_keep_history_range')
	get_date = roxy_wi_tools.GetDate()
	cur_date = get_date.return_date('regular', timedelta_minus=time_period)
	try:
		ActionHistory.delete().where(ActionHistory.date < cur_date).execute()
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
