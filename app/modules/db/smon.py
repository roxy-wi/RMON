import uuid
from datetime import datetime
from typing import Union

from peewee import fn

from app.modules.db.db_model import (
	SmonAgent, Server, SMON, SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck, SmonHistory, SmonStatusPageCheck,
	SmonStatusPage, SmonGroup, SmonSMTPCheck
)
from app.modules.db.common import out_error
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


def get_enabled_agents(group_id: int):
	try:
		return SmonAgent.select(SmonAgent, Server).join(Server).where(
			(Server.group_id == group_id) &
			(SmonAgent.enabled == True) |
			(SmonAgent.shared == 1)
		).objects().execute()
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
		check_type = SMON.get(SMON.id == check_id).check_type
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound(f'Id {check_id} not found')

	correct_model = tool_common.get_model_for_check(check_type=check_type)

	try:
		return correct_model.get(correct_model.smon_id == check_id).agent_id
	except correct_model.DoesNotExist:
		raise RoxywiResourceNotFound(f'{check_type} not found with id {check_id}')


def add_agent(**kwargs) -> int:
	try:
		last_id = SmonAgent.insert(**kwargs).execute()
		return last_id
	except Exception as e:
		out_error(e)


def delete_agent(agent_id: int):
	try:
		SmonAgent.delete().where(SmonAgent.id == agent_id).execute()
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


def get_agent_id_by_uuid(agent_uuid: int) -> int:
	try:
		return SmonAgent.get(SmonAgent.uuid == agent_uuid).id
	except Exception as e:
		out_error(e)


def get_agent_id_by_ip(agent_ip) -> int:
	try:
		return SmonAgent.get(SmonAgent.server_id == Server.get(Server.ip == agent_ip).server_id).id
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
		return model.select(model, SMON).join_from(model, SMON).where((SMON.enabled == '1') & (model.agent_id == agent_id)).execute()
	except Exception as e:
		out_error(e)


def select_status(smon_id):
	try:
		query_res = SMON.get(SMON.id == smon_id).status
	except Exception as e:
		out_error(e)
	else:
		return int(query_res)


def change_status(status, smon_id):
	query = SMON.update(status=status).where(SMON.id == smon_id)
	try:
		query.execute()
	except Exception as e:
		out_error(e)
		return False
	else:
		return True


def response_time(time, smon_id):
	query = SMON.update(response_time=time).where(SMON.id == smon_id)
	try:
		query.execute()
	except Exception as e:
		out_error(e)
		return False
	else:
		return True


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


def insert_smon(name, enable, group_id, desc, telegram, slack, pd, mm, user_group, check_type, timeout):
	try:
		last_id = SMON.insert(
			name=name, enabled=enable, desc=desc, group_id=group_id, telegram_channel_id=telegram, slack_channel_id=slack,
			pd_channel_id=pd, mm_channel_id=mm, user_group=user_group, status='3', check_type=check_type, check_timeout=timeout
		).execute()
		return last_id
	except Exception as e:
		out_error(e)


def insert_smon_ping(smon_id, hostname, packet_size, interval, agent_id):
	try:
		SmonPingCheck.insert(smon_id=smon_id, ip=hostname, packet_size=packet_size, interval=interval, agent_id=agent_id).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_smtp(smon_id, hostname, port, username, password, interval, agent_id, ignore_ssl_error):
	try:
		SmonSMTPCheck.insert(
			smon_id=smon_id, ip=hostname, port=port, username=username, password=password, interval=interval, agent_id=agent_id, ignore_ssl_error=ignore_ssl_error
		).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_tcp(smon_id, hostname, port, interval, agent_id):
	try:
		SmonTcpCheck.insert(smon_id=smon_id, ip=hostname, port=port, interval=interval, agent_id=agent_id).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_dns(smon_id: int, hostname: str, port: int, resolver: str, record_type: str, interval: int, agent_id: int) -> None:
	try:
		SmonDnsCheck.insert(
			smon_id=smon_id, ip=hostname, port=port, resolver=resolver, record_type=record_type, interval=interval, agent_id=agent_id
		).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def insert_smon_http(smon_id, url, body, http_method, interval, agent_id, body_req, header_req, status_code, ignore_ssl_error):
	try:
		SmonHttpCheck.insert(
			smon_id=smon_id, url=url, body=body, method=http_method, interval=interval, agent_id=agent_id, body_req=body_req,
			headers=header_req, accepted_status_codes=status_code, ignore_ssl_error=ignore_ssl_error
		).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def select_smon_checks(check_type: str, group_id: int) -> Union[SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck]:
	correct_model = tool_common.get_model_for_check(check_type=check_type)
	try:
		query = correct_model.select().join(SMON).where(SMON.user_group == group_id)
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


def delete_smon(smon_id, user_group):
	try:
		SMON.delete().where((SMON.id == smon_id) & (SMON.user_group == user_group)).execute()
	except SMON.DoesNotExist:
		raise RoxywiResourceNotFound
	except Exception as e:
		out_error(e)
		return False
	else:
		return True


def smon_list(user_group):
	if user_group == 1:
		query = (SMON.select().order_by(SMON.group_id))
	else:
		query = (SMON.select().where(SMON.user_group == user_group).order_by(SMON.group_id))

	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		return query_res


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


def select_status_page_by_id(page_id: int):
	try:
		query_res = SmonStatusPage.select().where(SmonStatusPage.id == page_id).execute()
	except Exception as e:
		return out_error(e)
	else:
		return query_res


def select_status_page(slug: str):
	try:
		query_res = SmonStatusPage.select().where(SmonStatusPage.slug == slug).execute()
	except Exception as e:
		out_error(e)
	else:
		return query_res


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
		return SmonHistory.select().where(SmonHistory.smon_id == smon_id).limit(limit).order_by(SmonHistory.date.desc()).execute()
	except Exception as e:
		out_error(e)


def update_check(smon_id, name, telegram, slack, pd, mm, group_id, desc, en, timeout):
	query = (SMON.update(
		name=name, telegram_channel_id=telegram, slack_channel_id=slack, pd_channel_id=pd, mm_channel_id=mm,
		group_id=group_id, desc=desc, enabled=en, updated_at=datetime.now(), check_timeout=timeout
	).where(SMON.id == smon_id))
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def update_check_agent(smon_id: int, agent_id: int, check_type: str) -> None:
	correct_model = tool_common.get_model_for_check(check_type=check_type)
	try:
		return correct_model.update(agent_id=agent_id).where(correct_model.smon_id == smon_id).execute()
	except Exception as e:
		out_error(e)


def update_check_http(smon_id, url, body, method, interval, agent_id, body_req, header_req, status_code):
	try:
		SmonHttpCheck.update(
			url=url, body=body, method=method, interval=interval, agent_id=agent_id, body_req=body_req, headers=header_req, accepted_status_codes=status_code
		).where(SmonHttpCheck.smon_id == smon_id).execute()
		return True
	except Exception as e:
		out_error(e)
		return False


def update_check_tcp(smon_id, ip, port, interval, agent_id):
	try:
		SmonTcpCheck.update(ip=ip, port=port, interval=interval, agent_id=agent_id).where(SmonTcpCheck.smon_id == smon_id).execute()
		return True
	except Exception as e:
		out_error(e)
		return False


def update_check_ping(smon_id, ip, packet_size, interval, agent_id):
	try:
		SmonPingCheck.update(ip=ip, packet_size=packet_size, interval=interval, agent_id=agent_id).where(SmonPingCheck.smon_id == smon_id).execute()
		return True
	except Exception as e:
		out_error(e)
		return False


def update_check_dns(smon_id: int, ip: str, port: int, resolver: str, record_type: str, interval: int, agent_id: int):
	try:
		SmonDnsCheck.update(ip=ip, port=port, resolver=resolver, record_type=record_type, interval=interval,
							agent_id=agent_id).where(SmonDnsCheck.smon_id == smon_id).execute()
		return True
	except Exception as e:
		out_error(e)
		return False


def select_smon(user_group):
	if user_group == 1:
		query = SMON.select()
	else:
		query = SMON.select().where(SMON.user_group == user_group)
	try:
		query_res = query.execute()
	except Exception as e:
		out_error(e)
	else:
		return query_res


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
	query = SmonHistory.delete().where(SmonHistory.date < cur_date)
	try:
		query.execute()
	except Exception as e:
		out_error(e)


def select_checks_for_agent(agent_id: int, check_type: str) -> dict:
	correct_model = tool_common.get_model_for_check(check_type=check_type)
	try:
		return correct_model.select(correct_model, SMON).join(SMON).where(correct_model.agent_id == agent_id).objects().execute()
	except Exception as e:
		out_error(e)


def get_smon_group_by_name(user_group: int, name: str) -> int:
	try:
		return SmonGroup.select().where((SmonGroup.name == name) & (SmonGroup.user_group == user_group)).get().id
	except Exception:
		return 0


def get_smon_group_name_by_id(group_id: int) -> str:
	try:
		return SmonGroup.get(SmonGroup.id == group_id).name
	except Exception as e:
		out_error(e)


def add_smon_group(user_group: int, name: str) -> int:
	try:
		return SmonGroup.insert(name=name, user_group=user_group).on_conflict('replace').execute()
	except Exception as e:
		out_error(e)


def select_smon_groups(user_group: int) -> object:
	try:
		return SmonGroup.select().where(SmonGroup.user_group == user_group)
	except Exception as e:
		out_error(e)
