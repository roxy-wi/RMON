import json
from keyword import kwlist
from typing import Union, Optional

import pytz
import requests
from datetime import datetime
from flask import render_template, abort

import app.modules.db.sql as sql
import app.modules.db.smon as smon_sql
import app.modules.common.common as common
import app.modules.server.server as server_mod
import app.modules.tools.smon_agent as smon_agent
import app.modules.roxywi.common as roxywi_common
from app.modules.roxywi.exception import RoxywiCheckLimits
from app.modules.roxywi.class_models import HttpCheckRequest, DnsCheckRequest, PingCheckRequest, TcpCheckRequest, \
    SmtpCheckRequest, RabbitCheckRequest, CheckMetricsQuery


def create_check(
        json_data, group_id, check_type, multi_check_id: int, agent_id: int, region_id: int = None, country_id: int = None
) -> int:
    name = json_data.name.encode('utf-8')
    kwargs = {
        "enabled": json_data.enabled,
        "telegram_channel_id": json_data.telegram_channel_id,
        "slack_channel_id": json_data.slack_channel_id,
        "pd_channel_id": json_data.pd_channel_id,
        "mm_channel_id": json_data.mm_channel_id,
        "email_channel_id": json_data.email_channel_id,
        "check_timeout": json_data.check_timeout,
        "retries": json_data.retries,
        "multi_check_id": multi_check_id,
        "group_id": group_id,
        "check_type": check_type,
        "agent_id": agent_id,
        "region_id": region_id,
        "country_id": country_id,
        "status": '3'
    }
    last_id = smon_sql.insert_smon(**kwargs)
    roxywi_common.logger(f'A new check {name} has been created on Agent {agent_id}')

    return last_id


def send_new_check(
        last_id: int,
        data: Union[HttpCheckRequest, DnsCheckRequest, TcpCheckRequest, PingCheckRequest, SmtpCheckRequest, RabbitCheckRequest],
        agent_id: int
) -> None:
    agent_ip = smon_sql.select_server_ip_by_agent_id(agent_id)
    if isinstance(data, HttpCheckRequest):
        smon_agent.send_http_checks(agent_id, agent_ip, last_id)
    elif isinstance(data, DnsCheckRequest):
        smon_agent.send_dns_checks(agent_id, agent_ip, last_id)
    elif isinstance(data, TcpCheckRequest):
        smon_agent.send_tcp_checks(agent_id, agent_ip, last_id)
    elif isinstance(data, PingCheckRequest):
        smon_agent.send_ping_checks(agent_id, agent_ip, last_id)
    elif isinstance(data, SmtpCheckRequest):
        smon_agent.send_smtp_checks(agent_id, agent_ip, last_id)
    elif isinstance(data, RabbitCheckRequest):
        smon_agent.send_rabbit_checks(agent_id, agent_ip, last_id)


def create_http_check(data: HttpCheckRequest, check_id: int) -> Optional[tuple[dict, int]]:
    kwargs = {
        'smon_id': check_id,
        'url': data.url,
        'body': data.body,
        'method': data.method,
        'interval': data.interval,
        'body_req': data.body_req,
        'headers': data.header_req,
        'accepted_status_codes': data.accepted_status_codes,
        'ignore_ssl_error': data.ignore_ssl_error,
        'redirects': data.redirects,
        'auth': data.auth
    }
    try:
        smon_sql.insert_smon_http(**kwargs)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create HTTP check')


def create_dns_check(data: DnsCheckRequest, last_id: int) -> Optional[tuple[dict, int]]:
    try:
        smon_sql.insert_smon_dns(last_id, data.ip, data.port, data.resolver, data.record_type, data.interval)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create DNS check')


def create_ping_check(data: PingCheckRequest, last_id: int) -> Optional[tuple[dict, int]]:
    try:
        kwargs = {
            'smon_id': last_id,
            'ip': str(data.ip),
            'packet_size': data.packet_size,
            'interval': data.interval,
            'count_packets': data.count_packets
        }
        smon_sql.insert_smon_ping(**kwargs)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create Ping check')


def create_smtp_check(data: SmtpCheckRequest, last_id: int) -> Optional[tuple[dict, int]]:
    try:
        smon_sql.insert_smon_smtp(last_id, data.ip, data.port, data.username, data.password, data.interval, data.ignore_ssl_error)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create Ping check')


def create_rabbit_check(data: RabbitCheckRequest, last_id: int) -> Optional[tuple[dict, int]]:
    try:
        smon_sql.insert_smon_rabbit(last_id, data.ip, data.port, data.username, data.password, data.interval, data.ignore_ssl_error, data.vhost)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create Ping check')


def create_tcp_check(data: TcpCheckRequest, last_id: int) -> Optional[tuple[dict, int]]:
    try:
        smon_sql.insert_smon_tcp(last_id, data.ip, data.port, data.interval)
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create TCP check')


def update_smon(smon_id, json_data) -> None:
    try:
        kwargs = {
            'enabled': json_data.enabled,
            'telegram_channel_id': json_data.telegram_channel_id,
            'slack_channel_id': json_data.slack_channel_id,
            'pd_channel_id': json_data.pd_channel_id,
            'mm_channel_id': json_data.mm_channel_id,
            'email_channel_id': json_data.email_channel_id,
            'check_timeout': json_data.check_timeout,
            'retries': json_data.retries,
            'updated_at': common.get_present_time(),
        }
    except Exception as e:
        raise Exception(f'wrong data: {e}')

    try:
        agent_id_old = smon_sql.get_agent_id_by_check_id(smon_id)
        agent_ip = smon_sql.get_agent_ip_by_id(agent_id_old)
        smon_agent.delete_check(agent_id_old, agent_ip, smon_id)
    except Exception:
        pass

    try:
        smon_sql.update_check(smon_id, **kwargs)
    except Exception as e:
        raise Exception(f'here: {e}')


def disable_multi_check(multi_check_id: int, group_id: int) -> None:
    checks = smon_sql.select_multi_check(multi_check_id, group_id)
    for check in checks:
        delete_check_from_agent(check.id)
    smon_sql.disable_check(multi_check_id)


def delete_check_from_agent(smon_id: int) -> None:
    try:
        agent_id = smon_sql.get_agent_id_by_check_id(smon_id)
        server_ip = smon_sql.get_agent_ip_by_id(agent_id)
        smon_agent.delete_check(agent_id, server_ip, smon_id)
        roxywi_common.logging_without_user(
            f'Check {smon_id} has been deleted from Agent {agent_id}',
            level='info',
            extra={'check_id': smon_id, 'agent_id': agent_id})
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'Cannot delete check')


def delete_multi_check(smon_id: int, user_group: int):
    try:
        multi_check = smon_sql.select_multi_check(smon_id, user_group)
    except Exception as e:
        raise e
    for m in multi_check:
        delete_check_from_agent(m.id)
    try:
        smon_sql.delete_multi_check(smon_id, user_group)
    except Exception as e:
        raise e


def get_metrics(check_id: int, query: CheckMetricsQuery) -> dict:
    vm_select = sql.get_setting('victoria_metrics_select')
    rmon_name = sql.get_setting('rmon_name')
    req = f'{vm_select}/query_range?query={rmon_name}_metrics{{check_id="{check_id}"}}&step={query.step}&start={query.start}&end={query.end}'
    response = requests.get(req)

    return json.loads(response.text)


def history_metrics_from_vm(check_id: int, query: CheckMetricsQuery) -> dict:
    metrics = {'chartData': {}}
    metrics['chartData']['labels'] = ''
    metrics_from_vm = get_metrics(check_id, query)
    rmon_name = sql.get_setting('rmon_name')
    if metrics_from_vm['status'] == 'error':
        raise Exception(metrics_from_vm['error'])
    for metric in metrics_from_vm['data']['result']:
        labels = ''

        if metric['metric']['__name__'] == f'{rmon_name}_metrics':
            metrics['chartData'][metric['metric']['metric']] = ''
            for value in metric['values']:
                date_time = datetime.fromtimestamp(value[0], tz=pytz.UTC).strftime('%Y-%m-%d %H:%M:%S%z')
                labels += f'{date_time},'
                metrics['chartData'][metric['metric']['metric']] += f'{value[1]},'
        metrics['chartData']['labels'] = labels
    return metrics


def history_metrics(server_id: int, check_type_id: int) -> dict:
    metric = smon_sql.select_smon_history(server_id)
    metrics = {'chartData': {}}
    metrics['chartData']['labels'] = {}
    labels = ''
    response_time = ''
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
        response_time += f'{i.response_time},'
        if check_type_id in (2, 3):
            name_lookup += f'{i.name_lookup},'
            connect += f'{i.connect},'
            app_connect += f'{i.app_connect},'
            if check_type_id == 2:
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
    metrics['chartData']['response_time'] = response_time
    if check_type_id in (2, 3):
        metrics['chartData']['namelookup'] = name_lookup
        metrics['chartData']['connect'] = connect
        metrics['chartData']['appconnect'] = app_connect
        if check_type_id == 2:
            metrics['chartData']['pretransfer'] = pre_transfer
            metrics['chartData']['redirect'] = redirect
            metrics['chartData']['starttransfer'] = start_transfer
            metrics['chartData']['download'] = download

    return metrics


def check_uptime(smon_id: int) -> float:
    count_checks = smon_sql.get_smon_history_count_checks(smon_id)
    try:
        uptime = round(count_checks['up'] * 100 / count_checks['total'], 2)
    except Exception:
        uptime = 0

    return float(uptime)


def create_status_page(name: str, slug: str, desc: str, checks: list, styles: str, group_id: int) -> int:
    try:
        return smon_sql.add_status_page(name, slug, desc, group_id, checks, styles)
    except Exception as e:
        raise Exception(f'{e}')


def edit_status_page(page_id: int, name: str, slug: str, desc: str, checks: list, styles: str) -> None:
    smon_sql.delete_status_page_checks(page_id)

    try:
        smon_sql.add_status_page_checks(page_id, checks)
        smon_sql.edit_status_page(page_id, name, slug, desc, styles)
    except Exception as e:
        raise e


def show_status_page(slug: str) -> str:
    page = smon_sql.get_status_page(slug)
    checks_status = {}
    if not page:
        abort(404, 'Not found status page')

    checks = smon_sql.select_status_page_checks(page.id)

    for check in checks:
        name = ''
        desc = ''
        group = ''
        check_type = ''
        multi_check_id = int(check.multi_check_id.id)
        smon = smon_sql.select_one_smon_by_multi_check(multi_check_id)
        en = ''
        for s in smon:
            name = s.multi_check_id.name
            check_id = s.id
            uptime = check_uptime(check_id)
            desc = s.multi_check_id.description
            check_type = s.check_type
            en = s.enabled
            multi_check_id = s.multi_check_id
            if multi_check_id.check_group_id:
                group = smon_sql.get_smon_group_by_id(multi_check_id.check_group_id).name
            else:
                group = 'No group'

        checks_status[check_id] = {'uptime': uptime, 'name': name, 'description': desc, 'group': group,
                                   'check_type': check_type, 'en': en, 'multi_check_id': multi_check_id}

    return render_template('smon/status_page.html', page=page, checks_status=checks_status)


def avg_status_page_status(page_id: int) -> str:
    checks = smon_sql.select_status_page_checks(page_id)

    for check in checks:
        check_id = int(check.multi_check_id.id)
        if not smon_sql.get_last_smon_status_by_multi_check(check_id):
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
    checking_types = {'tcp': '1', 'http': '2', 'smtp': '3', 'ping': '4', 'dns': '5', 'rabbitmq': '6'}
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
    check_types = {1: 'tcp', 2: 'http', 4: 'ping', 5: 'dns', 6: 'rabbitmq'}
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
        roxywi_common.logger(f'Failed to get avg resp time: {e}', 'error')
        return 0
