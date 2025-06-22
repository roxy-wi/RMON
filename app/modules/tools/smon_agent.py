import uuid
from typing import Union

import requests
from requests import Response

import app.modules.db.sql as sql
import app.modules.db.smon as smon_sql
import app.modules.db.server as server_sql
import app.modules.roxywi.common as roxywi_common
from app.modules.service.installation import run_ansible_thread
from app.modules.roxywi.class_models import RmonAgent
from app.modules.roxywi.exception import RoxywiResourceNotFound


def generate_agent_inv(server_ip: str, action: str, agent_uuid: uuid, agent_port=5101) -> object:
    master_port = sql.get_setting('master_port')
    master_ip = sql.get_setting('master_ip')
    if not master_ip: raise Exception(' Master IP cannot be empty')
    if master_port == '': raise Exception(' Master port cannot be empty')
    if agent_port == '': raise Exception(' Agent port cannot be empty')
    inv = {"server": {"hosts": {}}}
    server_ips = [server_ip]
    inv['server']['hosts'][server_ip] = {
        'action': action,
        'agent_port': agent_port,
        'agent_uuid': agent_uuid,
        'master_ip': master_ip,
        'master_port': master_port,
    }

    return inv, server_ips


def check_agent_limit():
    user_subscription = roxywi_common.return_user_subscription()
    count_agents = smon_sql.count_agents()
    if user_subscription['user_plan'] == 'free' and count_agents >= 1:
        raise Exception(' You have reached limit for Free plan')
    elif user_subscription['user_plan'] == 'home' and count_agents >= 3:
        raise Exception(' You have reached limit for Home plan')
    elif user_subscription['user_plan'] == 'enterprise' and count_agents >= 10:
        raise Exception(' You have reached limit for Enterprise plan')


def add_agent(data: RmonAgent) -> Union[tuple[int, int], tuple[dict, int], None]:
    try:
        server_ip = server_sql.select_server_ip_by_id(data.server_id)
    except Exception as e:
        return roxywi_common.handle_json_exceptions(e, 'Cannot find the server'), 404
    try:
        _ = smon_sql.get_agent_id_by_ip(server_ip)
    except RoxywiResourceNotFound:
        pass
    else:
        return roxywi_common.handle_json_exceptions('', 'The agent is already installed the server'), 409
    agent_uuid = str(uuid.uuid4())
    check_agent_limit()
    agent_kwargs = data.model_dump(mode='json', exclude={'reconfigure': True})
    agent_kwargs['uuid'] = agent_uuid

    try:
        inv, server_ips = generate_agent_inv(server_ip, 'install', agent_uuid, data.port)
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'Cannot generate inventory')
    try:
        task_id = run_ansible_thread(inv, server_ips, 'rmon_agent', 'Agent', 'install')
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'Cannot install RMON agent')

    try:
        last_id = smon_sql.add_agent(**agent_kwargs)
        roxywi_common.logger('A new RMON agent has been created', 'info', keep_history=1, service='RMON')
        return last_id, task_id
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'Cannot create Agent')


def delete_agent(agent_id: int):
    try:
        server_ip = smon_sql.get_agent_ip_by_id(agent_id)
    except Exception as e:
        raise e
    agent_uuid = ''
    try:
        inv, server_ips = generate_agent_inv(server_ip, 'uninstall', agent_uuid)
        return run_ansible_thread(inv, server_ips, 'rmon_agent', 'Agent', 'delete')
    except Exception as e:
        raise e


def update_agent(agent_id: int, data: RmonAgent):
    json_data = data.model_dump(mode='python', exclude={'reconfigure': True, 'uuid': True}, exclude_none=True)

    try:
        smon_sql.update_agent(agent_id, **json_data)
    except Exception as e:
        raise e

    if data.reconfigure:
        return reconfigure_agent(agent_id)


def reconfigure_agent(agent_id: int):
    agent = smon_sql.get_agent_data(agent_id)
    server_ip = smon_sql.select_server_ip_by_agent_id(agent_id)
    try:
        inv, server_ips = generate_agent_inv(server_ip, 'install', agent.uuid, agent.port)
        return run_ansible_thread(inv, server_ips, 'rmon_agent', 'Agent', 'reconfigure')
    except Exception as e:
        raise e


def get_agent_headers(agent_id: int) -> dict:
    try:
        agent_uuid = smon_sql.get_agent_uuid(agent_id)
    except Exception as e:
        if str(e).find("agent not found") != -1:
            agent_uuid = None
        else:
            raise Exception(e)
    return {'Agent-UUID': str(agent_uuid), 'Content-Type': 'application/json'}


def send_get_request_to_agent(agent_id: int, server_ip: str, api_path: str) -> bytes:
    headers = get_agent_headers(agent_id)
    agent = smon_sql.get_agent_data(agent_id)
    try:
        req = requests.get(f'http://{server_ip}:{agent.port}/{api_path}', headers=headers, timeout=5)
        return req.content
    except Exception as e:
        roxywi_common.logger(f'Cannot get agent status: {e}', 'error')
        raise Exception(' Cannot get agent status')


def send_post_request_to_agent(agent_id: int, server_ip: str, api_path: str, json_data: object) -> Response:
    headers = get_agent_headers(agent_id)
    agent = smon_sql.get_agent_data(agent_id)
    try:
        req = requests.post(f'http://{server_ip}:{agent.port}/{api_path}', headers=headers, json=json_data, timeout=15)
        return req
    except Exception as e:
        raise e


def delete_check(agent_id: int, server_ip: str, check_id: int) -> None:
    headers = get_agent_headers(agent_id)
    agent = smon_sql.get_agent_data(agent_id)
    try:
        requests.delete(f'http://{server_ip}:{agent.port}/check/{check_id}', headers=headers, timeout=5)
    except requests.exceptions.HTTPError as e:
        roxywi_common.logger(f'Cannot delete check from agent: http error {e}', 'error')
    except requests.exceptions.ConnectTimeout:
        roxywi_common.logger('Cannot delete check from agent: connection timeout', 'error')
    except requests.exceptions.ConnectionError:
        roxywi_common.logger('Cannot delete check from agent: connection error', 'error')
    except Exception as e:
        raise Exception(f' Cannot delete check from Agent {server_ip}: {e}')


def send_check_to_agent(agent_id: int, server_ip: str, check_id: int, multi_check_id: int, request_data: dict) -> None:
    status_created = 201  # Introduced constant for clarity
    endpoint = f'check/{check_id}'  # Renamed variable for better clarity
    retries = 2  # Allowed attempts to send the request

    # Helper function to handle logging with a consistent message format
    def log_agent_error(res, retry: int) -> None:
        extra_info = {
            'check_id': check_id,
            'agent_id': agent_id,
            'multi_check_id': multi_check_id
        }
        roxywi_common.logging_without_user(
            f"Agent returned: {res.status_code} {res.text}. "
            f"Retry {retry} while sending check {check_id} to agent {agent_id}.",
            'warning',
            extra_info
        )

    for attempt in range(1, retries + 1):
        response = send_post_request_to_agent(agent_id, server_ip, endpoint, request_data)
        if response.status_code == status_created:  # Successfully created
            roxywi_common.logger(
                f'Check {check_id} sent to agent {agent_id} successfully',
                'info',
                additional_extra={'check_id': check_id, 'agent_id': agent_id, 'multi_check_id': multi_check_id}
            )
            return
        log_agent_error(response, attempt)

        if attempt == retries:  # On the final attempt, raise an exception
            raise Exception(response.text)


def send_tcp_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 1)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'tcp')
    for check in checks:
        json_data = {
            'check_type': 'tcp',
            'name': check.smon_id.name,
            'server_ip': check.ip,
            'port': check.port,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout
        }
        try:
            send_check_to_agent(agent_id, server_ip, check.smon_id, check.smon_id.multi_check_id, json_data)
        except Exception as e:
            roxywi_common.logging_without_user(f'Cannot send TCP check: {e}',
                                               'error',
                                               extra={'check_id': check.id, 'agent_id': agent_id, 'multi_check_id': check.smon_id.multi_check_id}
                                               )


def send_ping_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 4)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'ping')
    for check in checks:
        json_data = {
            'check_type': 'ping',
            'name': check.smon_id.name,
            'server_ip': check.ip,
            'packet_size': check.packet_size,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout,
            'count_packets': check.count_packets
        }
        try:
            send_check_to_agent(agent_id, server_ip, check.smon_id, check.smon_id.multi_check_id, json_data)
        except Exception as e:
            roxywi_common.logging_without_user(f'Cannot send Ping check: {e}',
                                               'error',
                                               extra={'check_id': check.id, 'agent_id': agent_id, 'multi_check_id': check.smon_id.multi_check_id}
                                               )


def send_dns_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 5)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'dns')
    for check in checks:
        json_data = {
            'check_type': 'dns',
            'name': check.smon_id.name,
            'server_ip': check.ip,
            'port': check.port,
            'record_type': check.record_type,
            'resolver': check.resolver,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout
        }
        try:
            send_check_to_agent(agent_id, server_ip, check.smon_id, check.smon_id.multi_check_id, json_data)
        except Exception as e:
            roxywi_common.logging_without_user(f'Cannot send DNS check: {e}',
                                               'error',
                                               extra={'check_id': check.id, 'agent_id': agent_id, 'multi_check_id': check.smon_id.multi_check_id}
                                               )


def send_http_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 2)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'http')
    for check in checks:
        body = check.body
        if body:
            try:
                body = check.body.replace("'", "")
            except Exception as e:
                roxywi_common.logger(f'Cannot parse body for check {check.id}: {e}', 'error', additional_extra={'check_id': check.id})
        json_data = {
            'check_type': 'http',
            'name': check.smon_id.name,
            'url': check.url,
            'http_method': check.method,
            'body': body,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout,
            'accepted_status_codes': check.accepted_status_codes,
            'ignore_ssl_error': check.ignore_ssl_error,
            'body_req': check.body_req,
            'headers': check.headers,
            'redirects': check.redirects,
            'auth': check.auth,
        }
        try:
            send_check_to_agent(agent_id, server_ip, check.smon_id, check.smon_id.multi_check_id, json_data)
        except Exception as e:
            roxywi_common.logging_without_user(f'Cannot send HTTP check: {e}',
                                               'error',
                                               extra={'check_id': check.id, 'agent_id': agent_id, 'multi_check_id': check.smon_id.multi_check_id}
                                               )


def send_smtp_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 3)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'smtp')
    for check in checks:
        json_data = {
            'check_type': 'smtp',
            'name': check.smon_id.name,
            'server': check.ip,
            'port': check.port,
            'username': check.username,
            'password': check.password,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout,
            'ignore_ssl_error': check.ignore_ssl_error,
        }
        try:
            send_check_to_agent(agent_id, server_ip, check.smon_id, check.smon_id.multi_check_id, json_data)
        except Exception as e:
            roxywi_common.logging_without_user(f'Cannot send SMTP check: {e}',
                                               'error',
                                               extra={'check_id': check.id, 'agent_id': agent_id, 'multi_check_id': check.smon_id.multi_check_id}
                                               )


def send_rabbit_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 6)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'rabbitmq')
    for check in checks:
        json_data = {
            'check_type': 'rabbitmq',
            'name': check.smon_id.name,
            'server': check.ip,
            'port': check.port,
            'username': check.username,
            'password': check.password,
            'vhost': check.vhost,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout,
            'ignore_ssl_error': check.ignore_ssl_error,
        }
        try:
            send_check_to_agent(agent_id, server_ip, check.smon_id, check.smon_id.multi_check_id, json_data)
        except Exception as e:
            roxywi_common.logging_without_user(f'Cannot send RabbitMQ checks: {e}',
                                               'error',
                                               extra={'check_id': check.id, 'agent_id': agent_id, 'multi_check_id': check.smon_id.multi_check_id}
                                               )


def send_checks(agent_id: int) -> None:
    server_ip = smon_sql.select_server_ip_by_agent_id(agent_id)
    try:
        send_tcp_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logger(f'Cannot send TCP checks: {e}', 'error')
    try:
        send_ping_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logger(f'Cannot send Ping checks: {e}', 'error')
    try:
        send_dns_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logger(f'Cannot send DNS checks: {e}', 'error')
    try:
        send_http_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logger(f'Cannot send HTTP checks: {e}', 'error')
    try:
        send_smtp_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logger(f'Cannot send SMTP checks: {e}', 'error')
    try:
        send_rabbit_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logger(f'Cannot send RabbitMQ checks: {e}', 'error')
