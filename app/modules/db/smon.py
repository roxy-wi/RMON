import uuid
from datetime import datetime
from typing import Union

from peewee import fn, IntegrityError

from app.modules.db.db_model import (
	SmonAgent, Server, SMON, SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck, SmonHistory, SmonStatusPageCheck,
	SmonStatusPage, SmonGroup, SmonSMTPCheck, SmonRabbitCheck, mysql_enable, MultiCheck
)
from app.modules.db.common import out_error, resource_not_empty
import app.modules.roxy_wi_tools as roxy_wi_tools
import app.modules.tools.common as tool_common
from app.modules.roxywi.exception import RoxywiResourceNotFound


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
			(SmonAgent.id == agent_id) *
			(Server.group_id == group_id)
		).objects().execute()
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
		last_id = SmonAgent.insert(**kwargs).execute()
		return last_id
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
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)
	else:
		for r in query_res:
			return r.ip
		raise RoxywiResourceNotFound


def get_agent_by_uuid(agent_uuid: int) -> SmonAgent:
	try:
		return SmonAgent.get(SmonAgent.uuid == agent_uuid)
	except Exception as e:
		out_error(e)


def get_agent_id_by_ip(agent_ip) -> int:
	try:
		return SmonAgent.get(SmonAgent.server_id == Server.get(Server.ip == agent_ip).server_id).id
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def get_randon_agent(region_id: int) -> SmonAgent:
	try:
		if mysql_enable == '1':
			agent = SmonAgent.select().where(SmonAgent.region_id == region_id).order_by(fn.Rand())
			return agent.get()
		else:
			agent = SmonAgent.select().where(SmonAgent.region_id == region_id).order_by(fn.Random())
			return agent.get()
	except SmonAgent.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def select_server_ip_by_agent_id(agent_id: int) -> str:
	try:
		return Server.get(Server.server_id == SmonAgent.get(SmonAgent.id == agent_id).server_id).ip
	except Exception as e:
		out_error(e)


def select_en_smon(agent_id: int, check_type: str) -> Union[SmonTcpCheck, SmonPingCheck, SmonDnsCheck, SmonHttpCheck, SmonSMTPCheck]:
	model = tool_common.get_model_for_check(check_type=check_type)
	try:
		return model.select(model, SMON).join_from(model, SMON).where((SMON.enabled == '1') & (SMON.agent_id == agent_id)).execute()
	except Exception as e:
		out_error(e)


def select_status(smon_id):
	try:
		return SMON.get(SMON.id == smon_id).status
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def change_status(status: int, smon_id: int) -> None:
	try:
		SMON.update(status=status).where(SMON.id == smon_id).execute()
	except Exception as e:
		out_error(e)


def response_time(time, smon_id):
	try:
		SMON.update(response_time=time).where(SMON.id == smon_id).execute()
	except Exception as e:
		out_error(e)


def add_sec_to_state_time(time, smon_id):
	query = SMON.update(time_state=time).where(SMON.id == smon_id)
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def insert_smon_history(smon_id: int, resp_time: float, status: int, check_id: int, mes: str, now_utc: datetime):
	try:
		SmonHistory.insert(smon_id=smon_id, response_time=resp_time, status=status, date=now_utc, check_id=check_id, mes=mes).execute()
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
		return correct_model.select(correct_model, SMON).join_from(correct_model, SMON).where(SMON.id == smon_id).execute()
	except correct_model.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def select_check_with_group(check_id: int, group_id: int) -> SMON:
	try:
		return SMON.get((SMON.group_id == group_id) & (SMON.id == check_id))
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def insert_smon(name, enable, desc, telegram, slack, pd, mm, group_id, check_type, timeout, agent_id, region_id, country_id, multi_check_id):
	try:
		last_id = SMON.insert(
			name=name, enabled=enable, description=desc, telegram_channel_id=telegram, slack_channel_id=slack,
			pd_channel_id=pd, mm_channel_id=mm, group_id=group_id, status='3', check_type=check_type, check_timeout=timeout,
			region_id=region_id, country_id=country_id, multi_check_id=multi_check_id, agent_id=agent_id
		).execute()
		return last_id
	except Exception as e:
		out_error(e)


def insert_smon_ping(smon_id, hostname, packet_size, interval):
	try:
		SmonPingCheck.insert(smon_id=smon_id, ip=hostname, packet_size=packet_size, interval=interval).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_smtp(smon_id, hostname, port, username, password, interval, ignore_ssl_error):
	try:
		SmonSMTPCheck.insert(
			smon_id=smon_id, ip=hostname, port=port, username=username, password=password, interval=interval, ignore_ssl_error=ignore_ssl_error
		).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_rabbit(smon_id, hostname, port, username, password, interval, ignore_ssl_error, vhost):
	try:
		SmonRabbitCheck.insert(
			smon_id=smon_id, ip=hostname, port=port, username=username, password=password, interval=interval,
			ignore_ssl_error=ignore_ssl_error, vhost=vhost
		).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_tcp(smon_id, hostname, port, interval):
	try:
		SmonTcpCheck.insert(smon_id=smon_id, ip=hostname, port=port, interval=interval).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_dns(smon_id: int, hostname: str, port: int, resolver: str, record_type: str, interval: int) -> None:
	try:
		SmonDnsCheck.insert(
			smon_id=smon_id, ip=hostname, port=port, resolver=resolver, record_type=record_type, interval=interval
		).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_http(smon_id, url, body, http_method, interval, body_req, header_req, status_code, ignore_ssl_error):
	try:
		SmonHttpCheck.insert(
			smon_id=smon_id, url=url, body=body, method=http_method, interval=interval, body_req=body_req,
			headers=header_req, accepted_status_codes=status_code, ignore_ssl_error=ignore_ssl_error
		).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def select_smon_checks(check_type: str, group_id: int) -> Union[SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck]:
	correct_model = tool_common.get_model_for_check(check_type=check_type)
	try:
		query = correct_model.select().join(SMON).where(SMON.group_id == group_id)
		return query.execute()
	except correct_model.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def select_smon_by_id(last_id):
	query = SMON.select().where(SMON.id == last_id)
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		return query_res


def delete_multi_check(check_id: int, group_id: int) -> None:
	try:
		MultiCheck.delete().where(
			(MultiCheck.id == check_id) &
			(MultiCheck.group_id == group_id)
		).execute()
	except MultiCheck.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def select_multi_check(multi_check_id: int, group_id: int) -> SMON:
	try:
		return SMON.select().join(MultiCheck).where(
			(SMON.group_id == group_id) &
			(SMON.multi_check_id == multi_check_id)
		).order_by(MultiCheck.check_group_id)
	except Exception as e:
		out_error(e)


def select_multi_checks(group_id: int) -> SMON:
	try:
		return SMON.select().join(MultiCheck).where(SMON.group_id == group_id).order_by(MultiCheck.check_group_id).group_by(SMON.multi_check_id)
	except Exception as e:
		out_error(e)


def select_one_multi_check_join(multi_check_id: int, check_type_id: int) -> SMON:
	correct_model = tool_common.get_model_for_check(check_type_id=check_type_id)
	try:
		return correct_model.select(correct_model, SMON).join_from(correct_model, SMON).where(
			SMON.multi_check_id == multi_check_id
		).group_by(SMON.multi_check_id)
	except correct_model.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def get_multi_check(check_id: int, group_id: int) -> SMON:
	try:
		return SMON.get(
			(SMON.group_id == group_id) &
			(SMON.multi_check_id == check_id)
		)
	except Exception as e:
		out_error(e)


def update_multi_check_group_id(check_id: int, check_group_id: int) -> None:
	try:
		MultiCheck.update(check_group_id=check_group_id).where(MultiCheck.id == check_id).execute()
	except MultiCheck.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def add_status_page(name: str, slug: str, desc: str, group_id: int, checks: list, styles: str) -> int:
	try:
		last_id = SmonStatusPage.insert(name=name, slug=slug, group_id=group_id, description=desc, custom_style=styles).execute()
	except Exception as e:
		if 'Duplicate entry' in str(e):
			raise Exception('error: The Slug is already taken, please enter another one')
		else:
			out_error(e)
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
			SmonStatusPageCheck.insert(page_id=page_id, check_id=int(check)).execute()
		except Exception as e:
			out_error(e)


def delete_status_page_checks(page_id: int) -> None:
	try:
		SmonStatusPageCheck.delete().where(SmonStatusPageCheck.page_id == page_id).execute()
	except Exception as e:
		out_error(e)


def select_status_pages(group_id: int):
	try:
		query_res = SmonStatusPage.select().where(SmonStatusPage.group_id == group_id).execute()
	except Exception as e:
		return out_error(e)
	else:
		return query_res


def select_status_page_with_group(page_id: int, group_id: int) -> SmonStatusPage:
	try:
		return SmonStatusPage.get((SmonStatusPage.group_id == group_id) & (SmonStatusPage.id == page_id))
	except SmonStatusPage.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def get_status_page(slug: str) -> SmonStatusPage:
	try:
		return SmonStatusPage.get(SmonStatusPage.slug == slug)
	except Exception as e:
		out_error(e)


def select_status_page_checks(page_id: int):
	try:
		query_res = SmonStatusPageCheck.select().where(SmonStatusPageCheck.page_id == page_id).execute()
	except Exception as e:
		out_error(e)
	else:
		return query_res


def delete_status_page(page_id):
	try:
		SmonStatusPage.delete().where(SmonStatusPage.id == page_id).execute()
	except Exception as e:
		out_error(e)


def get_last_smon_status_by_check(smon_id: int) -> object:
	query = SmonHistory.select().where(
		SmonHistory.smon_id == smon_id
	).limit(1).order_by(SmonHistory.date.desc())
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		try:
			for i in query_res:
				return i.status
		except Exception:
			return ''


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
		try:
			for i in query_res:
				return i.response_time
		except Exception:
			return ''


def get_smon_history_count_checks(smon_id: int) -> dict:
	count_checks_dict = {}
	query = SmonHistory.select(fn.Count(SmonHistory.status)).where(
		SmonHistory.smon_id == smon_id
	)
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		try:
			for i in query_res:
				count_checks_dict['total'] = i.status
		except Exception as e:
			raise Exception(f'error: {e}')

	query = SmonHistory.select(fn.Count(SmonHistory.status)).where(
		(SmonHistory.smon_id == smon_id) &
		(SmonHistory.status == 1)
	)
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		try:
			for i in query_res:
				count_checks_dict['up'] = i.status
		except Exception as e:
			raise Exception(f'error: {e}')

	return count_checks_dict


def get_smon_service_name_by_id(smon_id: int) -> str:
	query = SMON.select().join(SmonHistory, on=(SmonHistory.smon_id == SMON.id)).where(SmonHistory.smon_id == smon_id)
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		try:
			for i in query_res:
				return f'{i.name}'
		except Exception:
			return ''


def select_smon_history(smon_id: int, limit: int = 40) -> SmonHistory:
	try:
		return SmonHistory.select().where(SmonHistory.smon_id == smon_id).limit(limit).order_by(SmonHistory.date.desc())
	except Exception as e:
		out_error(e)


def get_history(smon_id: int) -> SmonHistory:
	try:
		return SmonHistory.select().where(SmonHistory.smon_id == smon_id).order_by(SmonHistory.date.desc()).get()
	except SmonHistory.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)


def update_check(smon_id, name, telegram, slack, pd, mm, desc, en, timeout):
	query = (SMON.update(
		name=name, telegram_channel_id=telegram, slack_channel_id=slack, pd_channel_id=pd, mm_channel_id=mm,
		description=desc, enabled=en, updated_at=datetime.now(), check_timeout=timeout
	).where(SMON.id == smon_id))
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def update_check_agent(smon_id: int, agent_id: int) -> None:
	try:
		return SMON.update(agent_id=agent_id).where(SMON.id == smon_id).execute()
	except Exception as e:
		out_error(e)


def get_avg_resp_time(smon_id: int, check_id: int) -> int:
	try:
		query_res = SmonHistory.select(fn.AVG(SmonHistory.response_time)).where(
			(SmonHistory.smon_id == smon_id) &
			(SmonHistory.check_id == check_id)
		).scalar()
	except Exception as e:
		out_error(e)
	else:
		return query_res


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
			alert_value = SMON.get(SMON.id == smon_id).ssl_expire_warning_alert
		else:
			alert_value = SMON.get(SMON.id == smon_id).ssl_expire_critical_alert
	except Exception as e:
		out_error(e)
	else:
		return alert_value


def change_body_status(status, smon_id):
	query = SMON.update(body_status=status).where(SMON.id == smon_id)
	try:
		query.execute()
	except Exception as e:
		out_error(e)
		return False
	else:
		return True


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


def get_smon_group_by_name(group_id: int, name: str) -> int:
	try:
		return SmonGroup.select().where((SmonGroup.name == name) & (SmonGroup.group_id == group_id)).get().id
	except Exception:
		return 0


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
		return SmonGroup.insert(name=name, group_id=group_id).on_conflict('replace').execute()
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


def create_mutli_check(group_id: int, entity_type: str, check_group_id: int) -> int:
	try:
		return MultiCheck.insert(group_id=group_id, entity_type=entity_type, check_group_id=check_group_id).execute()
	except Exception as e:
		out_error(e)
