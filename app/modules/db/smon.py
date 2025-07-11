import uuid
from datetime import datetime, timedelta
from typing import Union

from peewee import fn, IntegrityError, Case

from app.modules.db.db_model import (
	SmonAgent, Server, SMON, SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck, SmonHistory, SmonStatusPageCheck,
	SmonStatusPage, SmonGroup, SmonSMTPCheck, SmonRabbitCheck, mysql_enable, MultiCheck, pgsql_enable
)
from app.modules.db.common import out_error, resource_not_empty
import app.modules.roxy_wi_tools as roxy_wi_tools
import app.modules.tools.common as tool_common
from app.modules.roxywi.class_models import CheckFiltersQuery
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.tools.smon import disable_multi_check


def get_agents(group_id: int):
	try:
		return SmonAgent.select(SmonAgent, Server).join(Server).where(
			(Server.group_id == group_id) |
			(SmonAgent.shared == 1)
		).objects().execute()
	except Exception as e:
		out_error(e)


def get_agents_by_region(region_id: int):
	try:
		return SmonAgent.select(SmonAgent).where(SmonAgent.region_id == region_id).execute()
	except Exception as e:
		out_error(e)


def get_free_servers_for_agent(group_id: int):
	try:
		query = Server.select().where(
			(Server.server_id.not_in(SmonAgent.select(SmonAgent.server_id))) &
			(Server.group_id == group_id)
		)
		return query.execute()
	except Exception as e:
		out_error(e)


def get_agent(agent_id: int):
	try:
		return SmonAgent.select(SmonAgent, Server).join(Server).where(SmonAgent.id == agent_id).objects().execute()
	except Exception as e:
		out_error(e)


def get_agent_with_group(agent_id: int, group_id: int):
	try:
		return SmonAgent.select(SmonAgent, Server).join(Server).where(
			(SmonAgent.id == agent_id) &
			((Server.group_id == group_id) | (SmonAgent.shared == 1))
		).objects().order_by(SmonAgent.id).execute()
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def get_agent_data(agent_id: int) -> SmonAgent:
	try:
		return SmonAgent.get(SmonAgent.id == agent_id)
	except Exception as e:
		out_error(e)


def get_agent_id_by_check_id(check_id: int):
	try:
		return SMON.get(SMON.id == check_id).agent_id
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound(f'Id {check_id} not found')
	except Exception as e:
		out_error(e)


def add_agent(**kwargs) -> int:
	try:
		return SmonAgent.insert(**kwargs).execute()
	except Exception as e:
		out_error(e)


def delete_agent(agent_id: int):
	try:
		SmonAgent.delete().where(SmonAgent.id == agent_id).execute()
	except IntegrityError:
		resource_not_empty()
	except Exception as e:
		out_error(e)


def update_agent(agent_id: int, **kwargs) -> None:
	try:
		SmonAgent.update(**kwargs).where(SmonAgent.id == agent_id).execute()
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def get_agent_uuid(agent_id: int) -> uuid:
	try:
		return SmonAgent.get(SmonAgent.id == agent_id).uuid
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def get_agent_ip_by_id(agent_id: int):
	try:
		query = SmonAgent.select(SmonAgent, Server).join(Server).where(SmonAgent.id == agent_id)
		query_res = query.objects().execute()
	except Exception as e:
		raise out_error(e, SmonAgent)
	else:
		for r in query_res:
			return r.ip
		raise RoxywiResourceNotFound


def get_agent_by_uuid(agent_uuid: int) -> SmonAgent:
	try:
		return SmonAgent.get(SmonAgent.uuid == agent_uuid)
	except Exception as e:
		raise out_error(e, SmonAgent)


def get_agent_id_by_ip(agent_ip) -> int:
	try:
		return SmonAgent.get(SmonAgent.server_id == Server.get(Server.ip == agent_ip).server_id).id
	except Exception as e:
		raise out_error(e, SmonAgent)


def get_randon_agent(region_id: int) -> int:
	try:
		if mysql_enable == '1':
			random_func = fn.Rand()  # MySQL uses Rand()
		else:
			random_func = fn.Random()

		agent = SmonAgent.select().where(SmonAgent.region_id == region_id).order_by(random_func)
		return agent.get()
	except Exception as e:
		raise out_error(e, SmonAgent)


def get_less_check_agent(region_id: int) -> int:
	try:
		result = (
			SmonAgent
			.select(SmonAgent, fn.COUNT(SMON.id).alias('checks_count'))
			.join(SMON)
			.where(SmonAgent.region_id == region_id)
			.group_by(SmonAgent.id)
			.order_by(fn.COUNT(SMON.id).asc())
			.limit(1)
		)
		return result.get()
	except Exception as e:
		raise out_error(e, SmonAgent)


def select_server_ip_by_agent_id(agent_id: int) -> str:
	try:
		return Server.get(Server.server_id == SmonAgent.get(SmonAgent.id == agent_id).server_id).ip
	except Exception as e:
		raise out_error(e, Server)


def select_en_smon(agent_id: int, check_type: str) -> Union[SmonTcpCheck, SmonPingCheck, SmonDnsCheck, SmonHttpCheck, SmonSMTPCheck]:
	model = tool_common.get_model_for_check(check_type=check_type)
	try:
		return model.select(model, SMON).join_from(model, SMON).where((SMON.enabled == '1') & (SMON.agent_id == agent_id)).execute()
	except Exception as e:
		raise out_error(e, model)


def change_status(status: int, smon_id: int, time: str) -> None:
	try:
		SMON.update(status=status, time_state=time).where(SMON.id == smon_id).execute()
	except Exception as e:
		out_error(e)


def response_time(time, smon_id):
	try:
		SMON.update(response_time=time).where(SMON.id == smon_id).execute()
	except Exception as e:
		out_error(e)


def insert_smon_history(**kwargs) -> None:
	if kwargs.get('status') == '':
		kwargs['status'] = 0
	if kwargs.get('response_time') == '':
		kwargs['response_time'] = 0
	try:
		SmonHistory.insert(**kwargs).execute()
	except Exception as e:
		out_error(e)


def insert_smon_history_http_metrics(date, **kwargs) -> None:
	try:
		query = (SmonHistory.update(kwargs).where(
			(SmonHistory.date == date) &
			(SmonHistory.smon_id == kwargs.get('smon_id'))
		))
		query.execute()
	except Exception as e:
		out_error(e)


def select_one_smon(smon_id: int, check_type_id: int) -> tuple:
	correct_model = tool_common.get_model_for_check(check_type_id=check_type_id)
	try:
		return correct_model.select(correct_model, SMON).join_from(correct_model, SMON).where(SMON.id == smon_id).order_by(SMON.id).execute()
	except correct_model.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		raise out_error(e)


def select_check_with_group(check_id: int, group_id: int) -> SMON:
	try:
		return SMON.get((SMON.group_id == group_id) & (SMON.id == check_id))
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		raise out_error(e)


def insert_smon(**kwargs):
	try:
		last_id = SMON.insert(**kwargs).execute()
		return last_id
	except Exception as e:
		out_error(e)


def insert_smon_ping(**kwargs):
	smon_id = kwargs.get('smon_id')
	try:
		SmonPingCheck.delete().where(SmonPingCheck.smon_id == smon_id).execute()
	except SmonPingCheck.DoesNotExist:
		print('There is no check, let\'s create')
	try:
		SmonPingCheck.insert(**kwargs).execute()
	except Exception as e:
		out_error(e)


def insert_smon_smtp(smon_id, hostname, port, username, password, interval, ignore_ssl_error):
	try:
		SmonSMTPCheck.delete().where(SmonSMTPCheck.smon_id == smon_id).execute()
	except SmonSMTPCheck.DoesNotExist:
		print('There is no check, let\'s create')
	try:
		SmonSMTPCheck.insert(
			smon_id=smon_id, ip=hostname, port=port, username=username, password=password, interval=interval, ignore_ssl_error=ignore_ssl_error
		).execute()
	except Exception as e:
		out_error(e)


def insert_smon_rabbit(smon_id, hostname, port, username, password, interval, ignore_ssl_error, vhost):
	try:
		SmonRabbitCheck.delete().where(SmonRabbitCheck.smon_id == smon_id).execute()
	except SmonRabbitCheck.DoesNotExist:
		print('There is no check, let\'s create')
	try:
		SmonRabbitCheck.insert(
			smon_id=smon_id, ip=hostname, port=port, username=username, password=password, interval=interval,
			ignore_ssl_error=ignore_ssl_error, vhost=vhost
		).execute()
	except Exception as e:
		out_error(e)


def insert_smon_tcp(smon_id, hostname, port, interval):
	try:
		SmonTcpCheck.delete().where(SmonTcpCheck.smon_id == smon_id).execute()
	except SmonTcpCheck.DoesNotExist:
		print('There is no check, let\'s create')
	try:
		SmonTcpCheck.insert(smon_id=smon_id, ip=hostname, port=port, interval=interval).execute()
	except Exception as e:
		out_error(e)


def insert_smon_dns(smon_id: int, hostname: str, port: int, resolver: str, record_type: str, interval: int) -> None:
	try:
		SmonDnsCheck.delete().where(SmonDnsCheck.smon_id == smon_id).execute()
	except SmonDnsCheck.DoesNotExist:
		print('There is no check, let\'s create')
	try:
		SmonDnsCheck.insert(
			smon_id=smon_id, ip=hostname, port=port, resolver=resolver, record_type=record_type, interval=interval
		).execute()
	except Exception as e:
		out_error(e)


def insert_smon_http(**kwargs):
	smon_id = kwargs.get('smon_id')
	try:
		SmonHttpCheck.delete().where(SmonHttpCheck.smon_id == smon_id).execute()
	except SmonHttpCheck.DoesNotExist:
		print('There is no check, let\'s create')
	try:
		SmonHttpCheck.insert(**kwargs).execute()
	except Exception as e:
		out_error(e)


def select_smon_by_id(last_id):
	try:
		return SMON.select().where(SMON.id == last_id).execute()
	except Exception as e:
		raise out_error(e, SMON)


def delete_multi_check(check_id: int, group_id: int) -> None:
	try:
		MultiCheck.delete().where(
			(MultiCheck.id == check_id) &
			(MultiCheck.group_id == group_id)
		).execute()
	except Exception as e:
		raise out_error(e, MultiCheck)


def select_multi_check(multi_check_id: int, group_id: int) -> SMON:
	try:
		return SMON.select().join(MultiCheck).where(
			(SMON.group_id == group_id) &
			(SMON.multi_check_id == multi_check_id)
		).order_by(MultiCheck.check_group_id).execute()
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		raise out_error(e, MultiCheck)


def select_one_smon_by_multi_check(multi_check_id: int) -> SMON:
	try:
		return SMON.select().join(MultiCheck).where(SMON.multi_check_id == multi_check_id).order_by(MultiCheck.check_group_id).limit(1).execute()
	except Exception as e:
		raise out_error(e, SMON)


def select_multi_checks(group_id: int) -> SMON:
	try:
		if pgsql_enable == '1':
			return SMON.select().join(MultiCheck).where(SMON.group_id == group_id).distinct(SMON.multi_check_id)
		else:
			return SMON.select().join(MultiCheck).where(SMON.group_id == group_id).order_by(MultiCheck.check_group_id).group_by(SMON.multi_check_id)
	except Exception as e:
		raise out_error(e, SMON)


def select_multi_checks_with_type(check_type: int, group_id: int) -> SMON:
	try:
		if pgsql_enable == '1':
			return SMON.select().join(MultiCheck).where(
				(SMON.group_id == group_id) &
				(SMON.check_type == check_type)
			).distinct(SMON.multi_check_id)
		return SMON.select().join(MultiCheck).where(
			(SMON.group_id == group_id) &
			(SMON.check_type == check_type)
		).order_by(MultiCheck.check_group_id).group_by(SMON.multi_check_id)
	except Exception as e:
		raise out_error(e, SMON)


def select_multi_check_with_filters(group_id: int, query: CheckFiltersQuery) -> SMON:
	where_query = (SMON.group_id == group_id)
	sort_query = None
	is_desc = False
	if any((query.check_name, query.check_group, query.check_type)):
		if query.check_name:
			where_query = where_query & (SMON.name.contains(query.check_name))
		if query.check_type:
			where_query = where_query & (SMON.check_type == query.check_type)
		if query.check_group:
			check_group_id = get_smon_group_by_name(group_id, query.check_group)
			where_query = where_query & (MultiCheck.check_group_id == check_group_id)
	if isinstance(query.check_status, int):
		where_query = where_query & (SMON.status == query.check_status)
	if query.sort_by:
		if query.sort_by.startswith('-'):
			is_desc = True
			query.sort_by = query.sort_by.replace('-', '')
		sorts = {
			'name': SMON.name,
			'status': SMON.status,
			'check_type': SMON.check_type,
			'check_group': MultiCheck.check_group_id,
			'created_at': SMON.created_at,
			'updated_at': SMON.updated_at,
		}
		if is_desc:
			sort_query = sorts[query.sort_by].desc()
		else:
			sort_query = sorts[query.sort_by].asc()
	try:
		if pgsql_enable == '1':
			if sort_query:
				query = SMON.select().join(MultiCheck).distinct(SMON.multi_check_id, sort_query).where(where_query).order_by(sort_query, SMON.multi_check_id).paginate(query.offset, query.limit)
			else:
				query = SMON.select().join(MultiCheck).where(where_query).distinct(SMON.multi_check_id).paginate(query.offset, query.limit)
		else:
			if sort_query:
				query = SMON.select().join(MultiCheck).where(where_query).order_by(sort_query).group_by(SMON.multi_check_id).paginate(query.offset, query.limit)
			else:
				query = SMON.select().join(MultiCheck).where(where_query).order_by(SMON.multi_check_id).group_by(SMON.multi_check_id).paginate(query.offset, query.limit)
		return query
	except Exception as e:
		raise out_error(e, SMON)


def get_count_multi_with_status_checks(group_id: int, status: int) -> int:
	try:
		if pgsql_enable == '1':
			return SMON.select().join(MultiCheck).where((SMON.group_id == group_id) & (SMON.status == status)).distinct(SMON.multi_check_id).count()
		else:
			return SMON.select().join(MultiCheck).where((SMON.group_id == group_id) & (SMON.status == status)).order_by(MultiCheck.check_group_id).group_by(SMON.multi_check_id).count()
	except Exception as e:
		raise out_error(e, SMON)


def get_count_multi_checks(group_id: int) -> int:
	try:
		if pgsql_enable == '1':
			return SMON.select().join(MultiCheck).where(SMON.group_id == group_id).distinct(SMON.multi_check_id).count()
		else:
			return SMON.select().join(MultiCheck).where(SMON.group_id == group_id).order_by(MultiCheck.check_group_id).group_by(SMON.multi_check_id).count()
	except Exception as e:
		raise out_error(e, SMON)


def select_one_multi_check_join(multi_check_id: int, check_type_id: int) -> SMON:
	correct_model = tool_common.get_model_for_check(check_type_id=check_type_id)
	try:
		if pgsql_enable == '1':
			return correct_model.select(correct_model, SMON).join_from(correct_model, SMON).distinct(SMON.multi_check_id).where(
				SMON.multi_check_id == multi_check_id
			)
		else:
			return correct_model.select(correct_model, SMON).join_from(correct_model, SMON).where(
				SMON.multi_check_id == multi_check_id
			).group_by(SMON.multi_check_id)
	except Exception as e:
		raise out_error(e, correct_model)


def get_multi_check(check_id: int, group_id: int) -> SMON:
	try:
		return SMON.get(
			(SMON.group_id == group_id) &
			(SMON.multi_check_id == check_id)
		)
	except Exception as e:
		raise out_error(e, SMON)


def get_one_multi_check(check_id: int) -> MultiCheck:
	try:
		return MultiCheck.get(MultiCheck.id == check_id)
	except Exception as e:
		raise out_error(e, MultiCheck)


def update_multi_check_group(check_id: int, **kwargs) -> None:
	try:
		MultiCheck.update(**kwargs).where(MultiCheck.id == check_id).execute()
	except Exception as e:
		raise out_error(e, MultiCheck)


def add_status_page(name: str, slug: str, desc: str, group_id: int, checks: list, styles: str) -> int:
	try:
		last_id = SmonStatusPage.insert(name=name, slug=slug, group_id=group_id, description=desc, custom_style=styles).execute()
	except Exception as e:
		if 'Duplicate entry' in str(e):
			raise Exception('error: The Slug is already taken, please, use another one')
		else:
			raise out_error(e)
	else:
		add_status_page_checks(last_id, checks)
		return last_id


def edit_status_page(page_id: int, name: str, slug: str, desc: str, styles: str) -> None:
	try:
		SmonStatusPage.update(name=name, slug=slug, description=desc, custom_style=styles).where(SmonStatusPage.id == page_id).execute()
	except Exception as e:
		out_error(e)


def add_status_page_checks(page_id: int, checks: list) -> None:
	for check in checks:
		try:
			SmonStatusPageCheck.insert(page_id=page_id, multi_check_id=int(check)).execute()
		except Exception as e:
			out_error(e)


def delete_status_page_checks(page_id: int) -> None:
	try:
		SmonStatusPageCheck.delete().where(SmonStatusPageCheck.page_id == page_id).execute()
	except Exception as e:
		out_error(e)


def select_status_pages(group_id: int):
	try:
		return SmonStatusPage.select().where(SmonStatusPage.group_id == group_id).execute()
	except Exception as e:
		return out_error(e)


def select_status_page_with_group(page_id: int, group_id: int) -> SmonStatusPage:
	try:
		return SmonStatusPage.get((SmonStatusPage.group_id == group_id) & (SmonStatusPage.id == page_id))
	except Exception as e:
		raise out_error(e, SmonStatusPage)


def get_status_page(slug: str) -> SmonStatusPage:
	try:
		return SmonStatusPage.get(SmonStatusPage.slug == slug)
	except Exception as e:
		raise out_error(e, SmonStatusPage)


def select_status_page_checks(page_id: int):
	try:
		return SmonStatusPageCheck.select().where(SmonStatusPageCheck.page_id == page_id).execute()
	except Exception as e:
		raise out_error(e, SmonStatusPage)


def delete_status_page(page_id):
	try:
		SmonStatusPage.delete().where(SmonStatusPage.id == page_id).execute()
	except Exception as e:
		out_error(e, SmonStatusPage)


def get_last_smon_status_by_multi_check(multi_check_id: int) -> object:
	try:
		smon_ids = SMON.select(SMON.id).where(SMON.multi_check_id == multi_check_id)

		query = (
			SmonHistory
			.select()
			.where(SmonHistory.smon_id.in_(smon_ids))
			.order_by(SmonHistory.date.desc())
			.limit(1)
		)

		for record in query:
			return record.status
		return ''
	except Exception as e:
		raise out_error(e, SMON)


def get_last_smon_res_time_by_check(smon_id: int, check_id: int) -> int:
	query = SmonHistory.select().where(
		(SmonHistory.smon_id == smon_id) &
		(SmonHistory.check_id == check_id)
	).limit(1).order_by(SmonHistory.date.desc())
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		for i in query_res:
			return i.response_time
	return 0


def get_smon_history_count_checks(smon_id: int) -> dict:
	"""
	Get counts of total checks and successful checks for a given smon_id.
	Optimized to use a single query with conditional counting.

	:param smon_id: The ID of the SMON check
	:return: Dictionary with 'total' and 'up' counts
	"""
	count_checks_dict = {'total': 0, 'up': 0}

	try:
		# Use a single query with conditional counting for better performance
		if mysql_enable == '1' or pgsql_enable == '1':
			# SQL databases support SUM with CASE
			query = SmonHistory.select(
				fn.Count(SmonHistory.smon_id).alias('total'),
				fn.SUM(Case(None, [(SmonHistory.status == 1, 1)], 0)).alias('up')
			).where(SmonHistory.smon_id == smon_id)
		else:
			# SQLite fallback - still more efficient than two separate queries
			query = SmonHistory.select(
				fn.Count(SmonHistory.smon_id).alias('total'),
				fn.Count(SmonHistory.smon_id).filter(SmonHistory.status == 1).alias('up')
			).where(SmonHistory.smon_id == smon_id)

		result = query.scalar(as_tuple=True)
		if result:
			count_checks_dict['total'] = result[0] or 0
			count_checks_dict['up'] = result[1] or 0
	except Exception as e:
		raise out_error(e)

	return count_checks_dict


def select_smon_history(smon_id: int, limit: int = 40) -> SmonHistory:
	"""
	Get the history records for a given smon_id with pagination.

	:param smon_id: The ID of the SMON check
	:param limit: Maximum number of records to return
	:return: Query result with history records
	"""
	try:
		# Using the composite index on (smon_id, date) for efficient filtering and sorting
		return SmonHistory.select(
			SmonHistory.smon_id,
			SmonHistory.check_id,
			SmonHistory.response_time,
			SmonHistory.status,
			SmonHistory.mes,
			SmonHistory.date,
			SmonHistory.name_lookup,
			SmonHistory.connect,
			SmonHistory.app_connect,
			SmonHistory.pre_transfer,
			SmonHistory.redirect,
			SmonHistory.start_transfer,
			SmonHistory.download
		).where(
			SmonHistory.smon_id == smon_id
		).limit(limit).order_by(SmonHistory.date.desc())
	except Exception as e:
		raise out_error(e, SmonHistory)


def get_history(smon_id: int) -> SmonHistory:
	try:
		return SmonHistory.select().where(SmonHistory.smon_id == smon_id).order_by(SmonHistory.date.desc()).get()
	except Exception as e:
		raise out_error(e, SmonHistory)


def update_check(smon_id, **kwargs) -> None:
	try:
		SMON.update(**kwargs).where(SMON.id == smon_id).execute()
	except Exception as e:
		raise out_error(e, SMON)


def update_check_agent(smon_id: int, agent_id: int) -> None:
	try:
		return SMON.update(agent_id=agent_id).where(SMON.id == smon_id).execute()
	except Exception as e:
		raise out_error(e, SMON)


def get_avg_resp_time(smon_id: int, check_id: int) -> int:
	try:
		query_res = SmonHistory.select(fn.AVG(SmonHistory.response_time)).where(
			(SmonHistory.smon_id == smon_id) &
			(SmonHistory.check_id == check_id)
		).scalar()
		return query_res if query_res is not None else 0
	except Exception as e:
		raise out_error(e, SmonHistory)


def update_smon_ssl_expire_date(smon_id: str, expire_date: str) -> None:
	try:
		SMON.update(ssl_expire_date=expire_date).where(SMON.id == smon_id).execute()
	except Exception as e:
		out_error(e)


def update_smon_alert_status(smon_id: str, alert_value: int, alert: str) -> None:
	if alert == 'ssl_expire_warning_alert':
		query = SMON.update(ssl_expire_warning_alert=alert_value).where(SMON.id == smon_id)
	else:
		query = SMON.update(ssl_expire_critical_alert=alert_value).where(SMON.id == smon_id)
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def get_smon_alert_status(smon_id: str, alert: str) -> int:
	try:
		if alert == 'ssl_expire_warning_alert':
			return SMON.get(SMON.id == smon_id).ssl_expire_warning_alert
		else:
			return SMON.get(SMON.id == smon_id).ssl_expire_critical_alert
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def get_smon(smon_id: int) -> SMON:
	try:
		return SMON.get(SMON.id == smon_id)
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def change_body_status(status, smon_id, time):
	try:
		SMON.update(body_status=status, time_state=time).where(SMON.id == smon_id).execute()
	except Exception as e:
		out_error(e)


def select_body_status(smon_id):
	try:
		query_res = SMON.get(SMON.id == smon_id).body_status
	except Exception as e:
		out_error(e)
	else:
		return query_res


def count_agents() -> int:
	try:
		return SmonAgent.select().count()
	except Exception as e:
		out_error(e)


def count_checks() -> int:
	try:
		return SMON.select().count()
	except Exception as e:
		out_error(e)


def delete_smon_history():
	get_date = roxy_wi_tools.GetDate()
	cur_date = get_date.return_date('regular', timedelta_minus=1)
	try:
		SmonHistory.delete().where(SmonHistory.date < cur_date).execute()
	except Exception as e:
		out_error(e)


def delete_smon(smon_id: int, group_id: int) -> None:
	try:
		SMON.delete().where((SMON.id == smon_id) & (SMON.group_id == group_id)).execute()
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def select_checks_for_agent(agent_id: int) -> dict:
	try:
		return SMON.select().where(SMON.agent_id == agent_id).execute()
	except Exception as e:
		out_error(e)


def select_checks_for_agent_by_check_type(agent_id: int, check_type: str) -> dict:
	correct_model = tool_common.get_model_for_check(check_type=check_type)
	try:
		return correct_model.select(correct_model, SMON).join(SMON).where(SMON.agent_id == agent_id).objects().execute()
	except Exception as e:
		out_error(e)


def select_checks_for_region_by_check_type(region_id: int, check_type: str) -> dict:
	correct_model = tool_common.get_model_for_check(check_type=check_type)
	try:
		return correct_model.select(correct_model, SMON).join(SMON).where(SMON.region_id == region_id).objects().execute()
	except Exception as e:
		out_error(e)


def select_checks_for_country_by_check_type(country_id: int, check_type: str) -> dict:
	correct_model = tool_common.get_model_for_check(check_type=check_type)
	try:
		return correct_model.select(correct_model, SMON).join(SMON).where(SMON.country_id == country_id).objects().execute()
	except Exception as e:
		out_error(e)


def get_smon_group_by_name(group_id: int, name: str) -> int:
	try:
		return SmonGroup.select().where((SmonGroup.name == name) & (SmonGroup.group_id == group_id)).get().id
	except SmonGroup.DoesNotExist:
		return 0
	except Exception as e:
		out_error(e)


def get_smon_group_by_id(check_group_id: int) -> SmonGroup:
	try:
		return SmonGroup.get(SmonGroup.id == check_group_id)
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def get_smon_group_by_id_with_group(check_group_id: int, group_id: int) -> SmonGroup:
	try:
		return SmonGroup.get((SmonGroup.id == check_group_id) & (SmonGroup.group_id == group_id))
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def add_smon_group(group_id: int, name: str) -> int:
	try:
		return SmonGroup.insert(name=name, group_id=group_id).execute()
	except Exception as e:
		out_error(e)


def update_smon_group(check_group_id: int, name: str, group_id: int) -> None:
	try:
		SmonGroup.update(name=name, group_id=group_id).where(SmonGroup.id == check_group_id).execute()
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def delete_smon_group(check_group_id: int, group_id: int) -> None:
	try:
		SmonGroup.delete().where((SmonGroup.id == check_group_id) & (SmonGroup.group_id == group_id)).execute()
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def select_smon_groups(group_id: int) -> object:
	try:
		return SmonGroup.select().where(SmonGroup.group_id == group_id)
	except Exception as e:
		out_error(e)


def create_multi_check(**kwargs) -> int:
	try:
		return MultiCheck.insert(**kwargs).execute()
	except Exception as e:
		out_error(e)


def update_check_current_retries(multi_check_id: int, current_retries: int) -> None:
	try:
		SMON.update(current_retries=current_retries).where(SMON.id == multi_check_id).execute()
	except Exception as e:
		out_error(e)


def disable_expired_check() -> None:
	try:
		multi_checks = MultiCheck.select(MultiCheck, SMON).join_from(MultiCheck, SMON).where(
			(SMON.enabled == 1) &
			(MultiCheck.expiration < datetime.now()) &
			(MultiCheck.expiration > datetime.now() - timedelta(minutes=5))
		)
	except Exception as e:
		out_error(e)
	try:
		for multi_check in multi_checks:
			disable_multi_check(multi_check.id, multi_check.group_id)
	except Exception as e:
		out_error(e)


def disable_check(multi_check_id: int) -> None:
	try:
		SMON.update(enabled=0).where(SMON.multi_check_id == multi_check_id).execute()
	except Exception as e:
		out_error(e)


def get_uptime_and_status(multi_check_id: int, group_id: int = None) -> dict:
	# Найти все SMON с этим multi_check_id
	if group_id is None:
		smon_q = SMON.select(SMON.id).where(SMON.multi_check_id == multi_check_id)
	else:
		smon_q = SMON.select(SMON.id).where((SMON.multi_check_id == multi_check_id) & (SMON.group_id == group_id))

	# Найти последние 40 записей из SmonHistory по этим SMON
	history_q = (
		SmonHistory
		.select()
		.where(SmonHistory.smon_id.in_(smon_q))
		.order_by(SmonHistory.date.desc())
		.limit(40)
	)

	history_entries = list(history_q)

	if not history_entries:
		return {
			'uptime': 0,
			'status': 0,
			'history': []
		}

	# Посчитать средний uptime (status == 1)
	total = len(history_entries)
	ok_count = sum(1 for entry in history_entries if entry.status == 1)
	uptime = ok_count / total

	# Определить общее состояние
	statuses = set(entry.status for entry in history_entries)

	if statuses == {1}:
		state = 1
	elif statuses == {0}:
		state = 0
	else:
		state = 2

	return {
		'uptime': round(uptime * 100, 2),  # в процентах
		'status': state,
		'history': [{'date': h.date, 'status': h.status, 'error': h.mes} for h in history_entries]
	}
