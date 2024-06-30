import json
from datetime import datetime
from typing import Union

from flask import render_template, abort

import app.modules.db.smon as smon_sql
import app.modules.common.common as common
import app.modules.server.server as server_mod
import app.modules.tools.smon_agent as smon_agent
import app.modules.roxywi.common as roxywi_common
from app.modules.roxywi.exception import RoxywiCheckLimits
from app.modules.roxywi.class_models import IdResponse, IdDataResponse, HttpCheckRequest, DnsCheckRequest, PingCheckRequest, TcpCheckRequest


def create_check(json_data, user_group, check_type, show_new=1) -> Union[bool, tuple]:
    try:
        name = json_data.name
        enable = json_data.enabled
        group = json_data.group
        desc = json_data.desc
        telegram = json_data.tg
        slack = json_data.slack
        pd = json_data.pd
        mm = json_data.mm
        timeout = json_data.timeout
    except Exception as e:
        raise e

    if group:
        smon_group_id = smon_sql.get_smon_group_by_name(user_group, group)
        if not smon_group_id:
            smon_group_id = smon_sql.add_smon_group(user_group, group)
    else:
        smon_group_id = None

    try:
        last_id = smon_sql.insert_smon(name, enable, smon_group_id, desc, telegram, slack, pd, mm, user_group, check_type, timeout)
    except Exception as e:
        print('error')
        return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot create check: {name}')

    if last_id:
        roxywi_common.logging('RMON', f'A new server {name} to RMON has been add', login=1)

    if last_id and show_new:
        return last_id
    else:
        return False


def send_new_check(last_id: int, data: Union[HttpCheckRequest, DnsCheckRequest, TcpCheckRequest, PingCheckRequest]) -> None:
    agent_ip = smon_sql.select_server_ip_by_agent_id(data.agent_id)
    if isinstance(data, HttpCheckRequest):
        smon_agent.send_http_checks(data.agent_id, agent_ip, last_id)
    elif isinstance(data, DnsCheckRequest):
        smon_agent.send_dns_checks(data.agent_id, agent_ip, last_id)
    elif isinstance(data, TcpCheckRequest):
        smon_agent.send_tcp_checks(data.agent_id, agent_ip, last_id)
    elif isinstance(data, PingCheckRequest):
        smon_agent.send_ping_checks(data.agent_id, agent_ip, last_id)


def create_http_check(data: HttpCheckRequest, check_id: int) -> tuple[dict, int]:
    try:
        smon_sql.insert_smon_http(
            check_id, data.url, data.body, data.http_method, data.interval, data.agent_id, data.body_req, data.header_req, data.accepted_status_codes
        )
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create HTTP check')


def create_dns_check(data: DnsCheckRequest, last_id: int) -> tuple[dict, int]:
    try:
        smon_sql.insert_smon_dns(last_id, data.ip, data.port, data.resolver, data.record_type, data.interval, data.agent_id)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create DNS check')


def create_ping_check(data: PingCheckRequest, last_id: int) -> tuple[dict, int]:
    try:
        smon_sql.insert_smon_ping(last_id, data.ip, data.packet_size, data.interval, data.agent_id)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create Ping check')


def create_tcp_check(data: TcpCheckRequest, last_id: int) -> tuple[dict, int]:
    try:
        smon_sql.insert_smon_tcp(last_id, data.ip, data.port, data.interval, data.agent_id)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create TCP check')


def update_smon(smon_id, json_data, user_group) -> None:
    print(json_data)
    try:
        name = json_data.name
        enabled = json_data.enabled
        group = json_data.group
        desc = json_data.desc
        telegram = json_data.tg
        slack = json_data.slack
        pd = json_data.pd
        mm = json_data.mm
        timeout = json_data.timeout
    except Exception as e:
        raise e

    try:
        agent_id_old = smon_sql.get_agent_id_by_check_id(smon_id)
        agent_ip = smon_sql.get_agent_ip_by_id(agent_id_old)
        smon_agent.delete_check(agent_id_old, agent_ip, smon_id)
    except Exception as e:
        raise e

    if group:
        smon_group_id = smon_sql.get_smon_group_by_name(user_group, group)
        if not smon_group_id:
            smon_group_id = smon_sql.add_smon_group(user_group, group)
    else:
        smon_group_id = None

    try:
        smon_sql.update_check(smon_id, name, telegram, slack, pd, mm, smon_group_id, desc, enabled, timeout)
            # if check_type == 'http':
            #     is_edited = smon_sql.update_check_http(smon_id, url, body, http_method, interval, agent_id, body_req, header_req, accepted_status_codes)
            # elif check_type == 'tcp':
            #     is_edited = smon_sql.update_check_tcp(smon_id, hostname, port, interval, agent_id)
            # elif check_type == 'ping':
            #     is_edited = smon_sql.update_check_ping(smon_id, hostname, packet_size, interval, agent_id)
            # elif check_type == 'dns':
            #     is_edited = smon_sql.update_check_dns(smon_id, hostname, port, resolver, record_type, interval, agent_id)
            #
            # if is_edited:
            #     roxywi_common.logging('RMON', f'The check {name} has been update', login=1)
            #     if not enabled:
            #         return 'Ok'
            #     try:
            #         api_path = f'check/{smon_id}'
            #         check_json = create_check_json(json_data)
            #         server_ip = smon_sql.select_server_ip_by_agent_id(agent_id)
            #         smon_agent.send_post_request_to_agent(agent_id, server_ip, api_path, check_json)
            #     except Exception as e:
            #         roxywi_common.handle_exceptions(e, 'RMON', f'Cannot add check to the agent {agent_ip}', loggin=1)
            #
            #     return "Ok"
    except Exception as e:
        raise Exception(f'Cannot update the server: {e}')


def delete_smon(smon_id: int, user_group: int):
    try:
        agent_id = smon_sql.get_agent_id_by_check_id(smon_id)
        server_ip = smon_sql.get_agent_ip_by_id(agent_id)
        smon_agent.delete_check(agent_id, server_ip, smon_id)
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'RMON', 'Cannot delete check', login=1)
    try:
        if smon_sql.delete_smon(smon_id, user_group):
            roxywi_common.logging('RMON', ' The server from RMON has been delete ', login=1)
    except Exception as e:
        raise e


def history_metrics(server_id: int, check_type_id: int) -> dict:
    metric = smon_sql.select_smon_history(server_id)

    metrics = {'chartData': {}}
    metrics['chartData']['labels'] = {}
    labels = ''
    curr_con = ''
    name_lookup = ''
    connect = ''
    app_connect = ''
    pre_transfer = ''
    redirect = ''
    start_transfer = ''
    download = ''

    for i in reversed(metric):
        date_time = common.get_time_zoned_date(i.date, '%H:%M:%S')
        labels += f'{date_time},'
        curr_con += f'{i.response_time},'
        if check_type_id == 2:
            name_lookup += f'{i.name_lookup},'
            connect += f'{i.connect},'
            app_connect += f'{i.app_connect},'
            pre_transfer += f'{i.pre_transfer},'
            try:
                if float(i.redirect) <= 0:
                    redirect += '0,'
                else:
                    redirect += f'{i.redirect},'
            except Exception:
                redirect += '0,'
            try:
                if float(i.start_transfer) <= 0:
                    start_transfer += '0,'
                else:
                    start_transfer += f'{i.start_transfer},'
            except Exception:
                start_transfer += '0,'
            download += f'{i.download},'

    metrics['chartData']['labels'] = labels
    metrics['chartData']['curr_con'] = curr_con
    if check_type_id == 2:
        metrics['chartData']['name_lookup'] = name_lookup
        metrics['chartData']['connect'] = connect
        metrics['chartData']['app_connect'] = app_connect
        metrics['chartData']['pre_transfer'] = pre_transfer
        metrics['chartData']['redirect'] = redirect
        metrics['chartData']['start_transfer'] = start_transfer
        metrics['chartData']['download'] = download

    return metrics


def history_statuses(dashboard_id: int) -> str:
    smon_statuses = smon_sql.select_smon_history(dashboard_id)

    return render_template('ajax/smon/history_status.html', smon_statuses=smon_statuses)


def history_cur_status(dashboard_id: int, check_id: int) -> str:
    cur_status = smon_sql.get_last_smon_status_by_check(dashboard_id)
    smon = smon_sql.select_one_smon(dashboard_id, check_id)

    return render_template('ajax/smon/cur_status.html', cur_status=cur_status, smon=smon)


def check_uptime(smon_id: int) -> int:
    count_checks = smon_sql.get_smon_history_count_checks(smon_id)

    try:
        uptime = round(count_checks['up'] * 100 / count_checks['total'], 2)
    except Exception:
        uptime = 0

    return uptime


def create_status_page(name: str, slug: str, desc: str, checks: list) -> str:
    group_id = roxywi_common.get_user_group(id=1)

    try:
        page_id = smon_sql.add_status_page(name, slug, desc, group_id, checks)
    except Exception as e:
        raise Exception(f'{e}')

    pages = smon_sql.select_status_page_by_id(page_id)

    return render_template('ajax/smon/status_pages.html', pages=pages)


def edit_status_page(page_id: int, name: str, slug: str, desc: str, checks: list) -> str:
    smon_sql.delete_status_page_checks(page_id)

    try:
        smon_sql.add_status_page_checks(page_id, checks)
        smon_sql.edit_status_page(page_id, name, slug, desc)
    except Exception as e:
        return f'error: Cannot update update status page: {e}'

    pages = smon_sql.select_status_page_by_id(page_id)

    return render_template('ajax/smon/status_pages.html', pages=pages)


def show_status_page(slug: str) -> str:
    page = smon_sql.select_status_page(slug)
    checks_status = {}
    if not page:
        abort(404, 'Not found status page')

    for p in page:
        page_id = p.id

    checks = smon_sql.select_status_page_checks(page_id)

    for check in checks:
        name = ''
        desc = ''
        group = ''
        check_type = ''
        check_id = str(check.check_id)
        smon = smon_sql.select_smon_by_id(check_id)
        uptime = check_uptime(check_id)
        en = ''
        for s in smon:
            name = s.name
            desc = s.desc
            check_type = s.check_type
            en = s.en
            if s.group_id:
                group = smon_sql.get_smon_group_name_by_id(s.group_id)
            else:
                group = 'No group'

        checks_status[check_id] = {'uptime': uptime, 'name': name, 'desc': desc, 'group': group,
                                   'check_type': check_type, 'en': en}

    return render_template('smon/status_page.html', page=page, checks_status=checks_status)


def avg_status_page_status(page_id: int) -> str:
    page_id = int(page_id)
    checks = smon_sql.select_status_page_checks(page_id)

    for check in checks:
        check_id = str(check.check_id)
        if not smon_sql.get_last_smon_status_by_check(check_id):
            return '0'

    return '1'


def check_checks_limit():
    user_subscription = roxywi_common.return_user_subscription()
    count_checks = smon_sql.count_checks()
    if user_subscription['user_plan'] == 'free' and count_checks >= 10:
        raise RoxywiCheckLimits('You have reached limit for Free plan')
    elif user_subscription['user_plan'] == 'home' and count_checks >= 30:
        raise RoxywiCheckLimits('You have reached limit for Home plan')
    elif user_subscription['user_plan'] == 'enterprise' and count_checks >= 100:
        raise RoxywiCheckLimits('You have reached limit for Enterprise plan')


def get_check_id_by_name(name: str) -> int:
    checking_types = {'tcp': '1', 'http': '2', 'ping': '4', 'dns': '5'}
    return checking_types[name]


def change_smon_port(new_port: int) -> None:
    cmd = f"sudo sed -i 's/\(^ExecStart.*$\)/ExecStart=gunicorn --workers 5 --bind 0.0.0.0:{new_port} -m 007 smon:app/' /etc/systemd/system/rmon-server.service"
    server_mod.subprocess_execute(cmd)
    cmd = 'sudo systemctl daemon-reload && sudo systemctl restart rmon-server'
    server_mod.subprocess_execute(cmd)


def get_ssl_expire_date(date: str) -> int:
    present = common.get_present_time()
    ssl_expire_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
    return (ssl_expire_date - present).days


def return_check_name_by_id(check_id: int) -> str:
    check_types = {1: 'tcp', 2: 'http', 4: 'ping', 5: 'dns'}
    return check_types[check_id]


def get_average_response_time(check_id: int, check_type_id: int) -> float:
    """
    Get the average response time for a given check ID and check type ID.

    Parameters:
    - check_type_id (int): The ID of the check.
    - check_type_id (int): The ID of the check type.

    Returns:
    - float: The average response time in seconds.
    """
    try:
        return round(smon_sql.get_avg_resp_time(check_id, check_type_id), 2)
    except Exception as e:
        roxywi_common.logging('RMON', f'Failed to get avg resp time: {e}')
        return 0
