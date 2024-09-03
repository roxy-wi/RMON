from typing import Union, Type

import distro

import app.modules.db.roxy as roxy_sql
import app.modules.roxywi.roxy as roxywi_mod
import app.modules.server.server as server_mod
from app.modules.db.db_model import SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck, SmonSMTPCheck, \
    SmonRabbitCheck


def get_services_status(update_cur_ver=0):
    services = []
    services_name = roxy_sql.get_all_tools()

    if update_cur_ver:
        try:
            update_cur_tool_versions()
        except Exception as e:
            raise Exception(f'error: Cannot update current versions: {e}')

    try:
        for s, v in services_name.items():
            status = is_tool_active(s)
            services.append([s, status, v])
    except Exception as e:
        raise Exception(f'error: Cannot get tools status: {e}')

    return services


def update_roxy_wi(service: str) -> str:
    restart_service = ''
    services = roxy_sql.get_roxy_tools()

    if service not in services and service != 'rmon':
        raise Exception(f'error: {service} is not part of RMON')

    if service != 'rmon':
        restart_service = f'&& sudo systemctl restart {service}'

    if distro.id() == 'ubuntu':
        cmd = f'sudo -S apt-get update && sudo apt-get install {service} -y {restart_service}'
    else:
        cmd = f'sudo -S yum -y install {service} {restart_service}'

    output, stderr = server_mod.subprocess_execute(cmd)
    update_cur_tool_version(service)

    if stderr != '':
        return str(stderr)
    else:
        return str(output)


def is_tool_active(tool_name: str) -> str:
    is_in_docker = roxywi_mod.is_docker()
    if is_in_docker:
        cmd = f"sudo supervisorctl status {tool_name}|awk '{{print $2}}'"
    else:
        cmd = f"systemctl is-active {tool_name}"
    status, stderr = server_mod.subprocess_execute(cmd)
    return status[0]


def update_cur_tool_versions() -> None:
    tools = roxy_sql.get_all_tools()
    for s, _v in tools.items():
        update_cur_tool_version(s)


def update_cur_tool_version(tool_name: str) -> None:
    correct_name = tool_name
    if distro.id() == 'ubuntu':
        cmd = f"apt list --installed 2>&1 |grep {correct_name}|awk '{{print $2}}'|sed 's/-/./'"
    else:
        cmd = f"rpm -q {correct_name}|awk -F\"{correct_name}\" '{{print $2}}' |awk -F\".noa\" '{{print $1}}' |sed 's/-//1' |sed 's/-/./'"

    service_ver, stderr = server_mod.subprocess_execute(cmd)

    try:
        service_ver = service_ver[0]
    except Exception:
        service_ver = 0

    if service_ver in ('command', 'prometheus:', 'not'):
        service_ver = 0

    try:
        roxy_sql.update_tool_cur_version(tool_name, service_ver)
    except Exception:
        pass


def get_cur_tool_version(tool_name: str) -> str:
    return roxy_sql.get_tool_cur_version(tool_name)


def get_model_for_check(
        check_type: str = None, check_type_id: int = None
) -> Type[Union[SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck, SmonSMTPCheck, SmonRabbitCheck]]:
    if check_type:
        check_models = {
            'tcp': SmonTcpCheck,
            'http': SmonHttpCheck,
            'dns': SmonDnsCheck,
            'ping': SmonPingCheck,
            'smtp': SmonSMTPCheck,
            'rabbitmq': SmonRabbitCheck
        }
    elif check_type_id:
        check_type = str(check_type_id)
        check_models = {
            '1': SmonTcpCheck,
            '2': SmonHttpCheck,
            '3': SmonSMTPCheck,
            '5': SmonDnsCheck,
            '4': SmonPingCheck,
            '6': SmonRabbitCheck,
        }
    else:
        raise Exception('Wrong check_type')
    return check_models[check_type]
