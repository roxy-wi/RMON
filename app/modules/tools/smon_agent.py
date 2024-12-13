import uuid
from typing import Union

import requests
import app.modules.db.sql as sql
import app.modules.db.smon as smon_sql
import app.modules.db.server as server_sql
import app.modules.roxywi.common as roxywi_common
from app.modules.service.installation import run_ansible
from app.modules.roxywi.class_models import RmonAgent
from app.modules.roxywi.exception import RoxywiResourceNotFound


def generate_agent_inv(server_ip: str, action: str, agent_uuid: uuid, agent_port=5101) -> object:
    master_port = sql.get_setting('master_port')
    master_ip = sql.get_setting('master_ip')
    if not master_ip: raise Exception('error: Master IP cannot be empty')
    if master_port == '': raise Exception('error: Master port cannot be empty')
    if agent_port == '': raise Exception('error: Agent port cannot be empty')
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
        raise Exception('error: You have reached limit for Free plan')
    elif user_subscription['user_plan'] == 'home' and count_agents >= 3:
        raise Exception('error: You have reached limit for Home plan')
    elif user_subscription['user_plan'] == 'enterprise' and count_agents >= 10:
        raise Exception('error: You have reached limit for Enterprise plan')


def add_agent(data: RmonAgent) -> Union[int, tuple]:
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
        roxywi_common.handle_exceptions(e, server_ip, 'Cannot generate inventory', login=1)
    try:
        run_ansible(inv, server_ips, 'rmon_agent')
    except Exception as e:
        roxywi_common.handle_exceptions(e, server_ip, 'Cannot install RMON agent', login=1)

    try:
        last_id = smon_sql.add_agent(**agent_kwargs)
        roxywi_common.logging(server_ip, 'A new RMON agent has been created', login=1, keep_history=1, service='RMON')
        return last_id
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'RMON server', 'Cannot create Agent', login=1)


def delete_agent(agent_id: int):
    try:
        server_ip = smon_sql.get_agent_ip_by_id(agent_id)
    except Exception as e:
        raise e
    agent_uuid = ''
    try:
        inv, server_ips = generate_agent_inv(server_ip, 'uninstall', agent_uuid)
        run_ansible(inv, server_ips, 'rmon_agent')
    except Exception as e:
        raise e


def update_agent(agent_id: int, data: RmonAgent):
    json_data = data.model_dump(mode='python', exclude={'reconfigure': True, 'uuid': True}, exclude_none=True)

    try:
        smon_sql.update_agent(agent_id, **json_data)
    except Exception as e:
        raise e

    if data.reconfigure:
        reconfigure_agent(agent_id)


def reconfigure_agent(agent_id: int):
    agent = smon_sql.get_agent_data(agent_id)
    server_ip = smon_sql.select_server_ip_by_agent_id(agent_id)
    try:
        inv, server_ips = generate_agent_inv(server_ip, 'install', agent.uuid, agent.port)
        run_ansible(inv, server_ips, 'rmon_agent')
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
    return {'Agent-UUID': str(agent_uuid)}


def send_get_request_to_agent(agent_id: int, server_ip: str, api_path: str) -> bytes:
    headers = get_agent_headers(agent_id)
    agent = smon_sql.get_agent_data(agent_id)
    try:
        req = requests.get(f'http://{server_ip}:{agent.port}/{api_path}', headers=headers, timeout=5)
        return req.content
    except Exception as e:
        roxywi_common.logging(server_ip, f'error: Cannot get agent status: {e}')
        raise Exception('error: Cannot get agent status')


def send_post_request_to_agent(agent_id: int, server_ip: str, api_path: str, json_data: object) -> bytes:
    headers = get_agent_headers(agent_id)
    agent = smon_sql.get_agent_data(agent_id)
    try:
        req = requests.post(f'http://{server_ip}:{agent.port}/{api_path}', headers=headers, json=json_data, timeout=5)
        return req.content
    except Exception as e:
        raise Exception(f'error: Cannot get agent status: {e}')


def delete_check(agent_id: int, server_ip: str, check_id: int) -> bytes:
    headers = get_agent_headers(agent_id)
    agent = smon_sql.get_agent_data(agent_id)
    try:
        req = requests.delete(f'http://{server_ip}:{agent.port}/check/{check_id}', headers=headers, timeout=5)
        return req.content
    except requests.exceptions.HTTPError as e:
        roxywi_common.logging(server_ip, f'error: Cannot delete check from agent: http error {e}', login=1)
    except requests.exceptions.ConnectTimeout:
        roxywi_common.logging(server_ip, 'error: Cannot delete check from agent: connection timeout', login=1)
    except requests.exceptions.ConnectionError:
        roxywi_common.logging(server_ip, 'error: Cannot delete check from agent: connection error', login=1)
    except Exception as e:
        raise Exception(f'error: Cannot delete check from Agent {server_ip}: {e}')


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
        api_path = f'check/{check.smon_id}'
        try:
            send_post_request_to_agent(agent_id, server_ip, api_path, json_data)
        except Exception as e:
            roxywi_common.handle_exceptions(e, 'RMON', 'Cannot send TCP check')


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
            'timeout': check.smon_id.check_timeout
        }
        api_path = f'check/{check.smon_id}'
        try:
            send_post_request_to_agent(agent_id, server_ip, api_path, json_data)
        except Exception as e:
            roxywi_common.handle_exceptions(e, 'RMON', 'Cannot send PING check')


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
        api_path = f'check/{check.smon_id}'
        try:
            send_post_request_to_agent(agent_id, server_ip, api_path, json_data)
        except Exception as e:
            roxywi_common.handle_exceptions(e, 'RMON', 'Cannot send DNS check')


def send_http_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 2)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'http')
    for check in checks:
        json_data = {
            'check_type': 'http',
            'name': check.smon_id.name,
            'url': check.url,
            'http_method': check.method,
            'body': check.body,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout,
            'accepted_status_codes': check.accepted_status_codes,
            'ignore_ssl_error': check.ignore_ssl_error,
            'body_req': check.body_req,
            'headers': check.headers,
        }

        api_path = f'check/{check.smon_id}'
        try:
            send_post_request_to_agent(agent_id, server_ip, api_path, json_data)
        except Exception as e:
            roxywi_common.handle_exceptions(e, 'RMON', 'Cannot send HTTP check')


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
        api_path = f'check/{check.smon_id}'
        try:
            send_post_request_to_agent(agent_id, server_ip, api_path, json_data)
        except Exception as e:
            roxywi_common.handle_exceptions(e, 'RMON', 'Cannot send SMTP check')


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
        api_path = f'check/{check.smon_id}'
        try:
            send_post_request_to_agent(agent_id, server_ip, api_path, json_data)
        except Exception as e:
            roxywi_common.handle_exceptions(e, 'RMON', 'Cannot send RabbitMQ check')


def send_checks(agent_id: int) -> None:
    server_ip = smon_sql.select_server_ip_by_agent_id(agent_id)
    try:
        send_tcp_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logging(f'Agent ID: {agent_id}', f'error: Cannot send TCP checks: {e}')
    try:
        send_ping_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logging(f'Agent ID: {agent_id}', f'error: Cannot send Ping checks: {e}')
    try:
        send_dns_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logging(f'Agent ID: {agent_id}', f'error: Cannot send DNS checks: {e}')
    try:
        send_http_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logging(f'Agent ID: {agent_id}', f'error: Cannot send HTTP checks: {e}')
    try:
        send_smtp_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logging(f'Agent ID: {agent_id}', f'error: Cannot send SMTP checks: {e}')
    try:
        send_rabbit_checks(agent_id, server_ip)
    except Exception as e:
        roxywi_common.logging(f'Agent ID: {agent_id}', f'error: Cannot send RabbitMQ checks: {e}')
