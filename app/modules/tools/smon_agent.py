import json
import uuid
import os
import re
from typing import Union

import requests
from requests import Response
from flask import current_app, has_app_context, has_request_context, request

import app.modules.db.sql as sql
import app.modules.db.smon as smon_sql
import app.modules.db.server as server_sql
import app.modules.roxywi.common as roxywi_common
from app.modules.subscription.access import MONITORING_AGENTS, enforce_resource_limit
from app.modules.service.installation import run_ansible, run_ansible_thread
from app.modules.roxywi.class_models import RmonAgent
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.roxy_wi_tools import GetConfigVar
from app.modules.common import agent_transport


def generate_agent_inv(server_ip: str, action: str, agent_uuid: uuid, agent_port=5101,
                       *, group_id=None, result_transport=None) -> object:
    config = GetConfigVar().config
    control_url = os.getenv('RMON_AGENT_CONTROL_URL') or config.get('agent_deployment', 'control_url', fallback='')
    if not control_url and has_app_context():
        control_url = current_app.config.get('PUBLIC_URL', '')
    if not control_url and has_request_context():
        control_url = request.url_root.rstrip('/')
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
        'agent_control_url': control_url,
        'agent_image': os.getenv('RMON_AGENT_IMAGE') or config.get(
            'agent_deployment', 'image', fallback='ghcr.io/roxy-wi/rmon/rmon-agent:2.0'),
    }

    for option in ('bind_ip', 'pull'):
        if config.has_option('agent_deployment', option):
            inv['server']['hosts'][server_ip]['agent_' + option] = config.get('agent_deployment', option)
    if action == 'install' and result_transport is not None:
        if group_id is None:
            raise ValueError('The agent owner group is required')
        inv['server']['hosts'][server_ip].update(
            agent_transport.inventory_settings(group_id, agent_uuid, result_transport))

    return inv, server_ips


def run_agent_action(agent_id: int, action: str):
    if action not in ('start', 'stop', 'restart'):
        raise ValueError('Unsupported agent action')
    agent = smon_sql.get_agent_data(agent_id)
    server_ip = smon_sql.get_agent_ip_by_id(agent_id)
    inventory = {'server': {'hosts': {server_ip: {'action': action, 'agent_uuid': str(agent.uuid)}}}}
    return run_ansible_thread(inventory, [server_ip], 'rmon_agent', 'Agent', action)


def check_agent_limit():
    count_agents = smon_sql.count_agents()
    enforce_resource_limit(MONITORING_AGENTS, count_agents)


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
    server = server_sql.get_server_by_ip(server_ip)
    mode = data.result_transport or agent_transport.group_settings(server.group_id)['agent_result_transport']
    agent_kwargs = data.model_dump(mode='json', exclude={'reconfigure': True})
    agent_kwargs['uuid'] = agent_uuid
    agent_kwargs['result_transport'] = mode

    try:
        inv, server_ips = generate_agent_inv(server_ip, 'install', agent_uuid, data.port,
                                             group_id=server.group_id, result_transport=mode)
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'Cannot generate inventory')
    try:
        last_id = smon_sql.add_agent(**agent_kwargs)
        try:
            task_id = run_ansible_thread(inv, server_ips, 'rmon_agent', 'Agent', 'install')
        except Exception:
            smon_sql.delete_agent(last_id)
            raise
        roxywi_common.logger('A new RMON agent has been created', 'info', keep_history=1, service='RMON')
        return last_id, task_id
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'Cannot create Agent')


def delete_agent(agent_id: int):
    try:
        server_ip = smon_sql.get_agent_ip_by_id(agent_id)
    except Exception as e:
        raise e
    agent_uuid = str(smon_sql.get_agent_data(agent_id).uuid)
    try:
        inv, server_ips = generate_agent_inv(server_ip, 'uninstall', agent_uuid)
        return run_ansible_thread(inv, server_ips, 'rmon_agent', 'Agent', 'delete')
    except Exception as e:
        raise e


def update_agent(agent_id: int, data: RmonAgent):
    agent = smon_sql.get_agent_data(agent_id)
    if data.server_id != agent.server_id_id:
        raise ValueError('An installed agent cannot be moved to another server')
    json_data = data.model_dump(mode='python', exclude={'reconfigure': True, 'uuid': True}, exclude_none=True)
    inv = None
    if data.reconfigure:
        mode = data.result_transport or agent.result_transport
        inv, server_ips = generate_agent_inv(agent.server_id.ip, 'install', agent.uuid, data.port,
                                             group_id=agent.server_id.group_id, result_transport=mode)
    try:
        smon_sql.update_agent(agent_id, **json_data)
    except Exception as e:
        raise e

    if data.reconfigure:
        return run_ansible_thread(inv, server_ips, 'rmon_agent', 'Agent', 'reconfigure')


def reconfigure_agent(agent_id: int):
    agent = smon_sql.get_agent_data(agent_id)
    server_ip = smon_sql.select_server_ip_by_agent_id(agent_id)
    try:
        inv, server_ips = generate_agent_inv(server_ip, 'install', agent.uuid, agent.port,
                                             group_id=agent.server_id.group_id,
                                             result_transport=agent.result_transport)
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
    server_ip = smon_sql.get_agent_ip_by_id(agent_id)
    try:
        req = requests.get(f'http://{server_ip}:{agent.port}/{api_path}', headers=headers, timeout=5)
        try:
            req.raise_for_status()
            return req.content
        finally:
            req.close()
    except requests.HTTPError:
        raise
    except Exception as e:
        roxywi_common.logger(f'Cannot get agent status: {e}', 'error')
        raise Exception(' Cannot get agent status')


def get_agent_health(agent_id: int, server_ip: str) -> dict:
    try:
        result = send_get_request_to_agent(agent_id, server_ip, 'health')
    except requests.HTTPError as error:
        if error.response is None or error.response.status_code != 404:
            raise
        # Older agents expose status only through Flask-APScheduler.
        result = send_get_request_to_agent(agent_id, server_ip, 'scheduler')
    data = json.loads(result)
    if not isinstance(data, dict) or not isinstance(data.get('running'), bool):
        raise ValueError('Invalid agent health response')
    return data


def send_post_request_to_agent(agent_id: int, server_ip: str, api_path: str, json_data: object) -> Response:
    headers = get_agent_headers(agent_id)
    agent = smon_sql.get_agent_data(agent_id)
    server_ip = smon_sql.get_agent_ip_by_id(agent_id)
    try:
        req = requests.post(f'http://{server_ip}:{agent.port}/{api_path}', headers=headers, json=json_data, timeout=15)
        return req
    except Exception as e:
        raise e


def delete_check(agent_id: int, server_ip: str, check_id: int) -> None:
    headers = get_agent_headers(agent_id)
    agent = smon_sql.get_agent_data(agent_id)
    server_ip = smon_sql.get_agent_ip_by_id(agent_id)
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
    server_ip = smon_sql.get_agent_ip_by_id(agent_id)
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
            'name': check.smon_id.multi_check_id.name,
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
            'name': check.smon_id.multi_check_id.name,
            'server_ip': check.ip,
            'packet_size': check.packet_size,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout,
            'count_packets': check.count_packets,
            'use_kernel_timestamp': check.use_kernel_timestamp
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
            'name': check.smon_id.multi_check_id.name,
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


def _require_http_policy_support(agent_id: int, server_ip: str) -> None:
    try:
        data = json.loads(send_get_request_to_agent(agent_id, server_ip, 'version'))
        version = data.get('version') if isinstance(data, dict) else None
        match = re.fullmatch(r'(\d+)\.(\d+)(?:\.\d+)?', version or '')
    except Exception as error:
        raise ValueError('Cannot verify agent support for HTTPS policy. Check the agent connection and try again.') from error
    if not match or tuple(map(int, match.group(1, 2))) < (1, 20):
        raise ValueError('HTTPS policy requires Agent 1.20 or later. Update the agent and resend the check.')


def send_http_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 2)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'http')
    checks = list(checks)
    policy_error = None
    if any(check.ssl_policy != 'default' for check in checks):
        try:
            _require_http_policy_support(agent_id, server_ip)
        except ValueError as error:
            policy_error = error
            # Continue synchronizing checks that do not need the optional feature.
            checks = [check for check in checks if check.ssl_policy == 'default']
    for check in checks:
        body = check.body
        if body:
            try:
                body = check.body.replace("'", "")
            except Exception as e:
                roxywi_common.logger(f'Cannot parse body for check {check.id}: {e}', 'error', additional_extra={'check_id': check.id})
        json_data = {
            'check_type': 'http',
            'name': check.smon_id.multi_check_id.name,
            'url': check.url,
            'http_method': check.method,
            'body': body,
            'body_json': check.body_json,
            'interval': check.interval,
            'timeout': check.smon_id.check_timeout,
            'accepted_status_codes': check.accepted_status_codes,
            'ignore_ssl_error': check.ignore_ssl_error,
            'body_req': check.body_req,
            'header_req': check.header_req,
            'redirects': check.redirects,
            'fail_if_not_ssl': check.ssl_policy == 'require_https',
            'fail_if_ssl': check.ssl_policy == 'require_http',
            'auth': check.auth,
            'proxy': check.proxy,
            'headers_response': check.headers_response,
            'http_version': check.http_version,
            'accept_cookies': check.accept_cookies,
            'resole_to_ip': check.resole_to_ip,
        }
        try:
            send_check_to_agent(agent_id, server_ip, check.smon_id, check.smon_id.multi_check_id, json_data)
        except Exception as e:
            roxywi_common.logging_without_user(f'Cannot send HTTP check: {e}',
                                               'error',
                                               extra={'check_id': check.id, 'agent_id': agent_id, 'multi_check_id': check.smon_id.multi_check_id}
                                               )
    if policy_error:
        raise policy_error


def send_smtp_checks(agent_id: int, server_ip: str, check_id=None) -> None:
    if check_id:
        checks = smon_sql.select_one_smon(check_id, 3)
    else:
        checks = smon_sql.select_en_smon(agent_id, 'smtp')
    for check in checks:
        json_data = {
            'check_type': 'smtp',
            'name': check.smon_id.multi_check_id.name,
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
            'name': check.smon_id.multi_check_id.name,
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
