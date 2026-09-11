from typing import Union, Type
import ast
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse

import distro
import requests
from packaging.version import InvalidVersion, Version

import app.modules.db.roxy as roxy_sql
import app.modules.roxywi.roxy as roxywi_mod
import app.modules.server.server as server_mod
from app.modules.db.db_model import SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck, SmonSMTPCheck, \
    SmonRabbitCheck


def get_services_status(update_cur_ver=0):
    services = []
    refreshed = {}

    if update_cur_ver:
        try:
            refreshed = update_cur_tool_versions()
        except Exception as e:
            raise Exception(f'error: Cannot update current versions: {e}')

    try:
        # Read after refresh: the first request must not render yesterday's values.
        services_name = roxy_sql.get_all_tools()
        for s, v in services_name.items():
            status = is_tool_active(s)
            v.update(refreshed.get(s, {}))
            current = _valid_version(v['current_version'])
            latest = _valid_version(v['new_version'])
            v.setdefault('version_known', current is not None)
            v.setdefault('installed', True if current else None)
            v['update_available'] = bool(current and latest and Version(current) < Version(latest))
            if os.getenv('RMON_CONTAINER') == '1':
                v['managed_by'] = 'external'
                if not (s == 'rmon-server' and os.getenv('RMON_SERVER_INTERNAL_URL')):
                    v.update(current_version='0', version_known=False, installed=None, update_available=False)
            services.append([s, status, v])
    except Exception as e:
        raise Exception(f'error: Cannot get tools status: {e}')

    return services


def update_roxy_wi(service: str) -> str:
    if os.getenv('RMON_CONTAINER') == '1':
        raise ValueError('error: Update container images or external services outside the RMON web container.')
    if service == 'rmon-server' and os.getenv('RMON_SERVER_INTERNAL_URL'):
        raise ValueError('error: This RMON Server is managed by Docker. Update its container image instead of installing an OS package.')
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
    if os.getenv('RMON_CONTAINER') == '1':
        return 'external'
    is_in_docker = roxywi_mod.is_docker()
    if is_in_docker:
        cmd = f"sudo supervisorctl status {tool_name}|awk '{{print $2}}'"
    else:
        cmd = f"systemctl is-active {tool_name}"
    status, stderr = server_mod.subprocess_execute(cmd)
    return status[0] if status else 'unknown'


def update_cur_tool_versions() -> dict:
    tools = roxy_sql.get_all_tools()
    versions = {}
    for s, _v in tools.items():
        versions[s] = update_cur_tool_version(s)
    return versions


def _valid_version(value) -> str | None:
    value = str(value or '').strip()
    if not value or value == '0' or len(value) > 100:
        return None
    try:
        Version(value)
    except InvalidVersion:
        return None
    return value


def _version_command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _source_version(directory: str) -> str | None:
    """Read version metadata without importing or executing the service's code."""
    try:
        path = Path(directory) / 'modules' / 'common' / 'version.py'
        if not path.is_absolute() or path.stat().st_size > 65536:
            return None
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == 'SERVICE_VERSION' for target in node.targets):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return _valid_version(node.value.value)
    except (OSError, SyntaxError, UnicodeError, ValueError):
        return None
    return None


def _server_runtime_version() -> str | None:
    """Read the explicitly configured receiver over HTTP, HTTPS or mTLS."""
    url = os.getenv('RMON_SERVER_INTERNAL_URL', '').rstrip('/')
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    try:
        token = Path(os.environ['RMON_SERVER_INTERNAL_TOKEN_FILE']).read_text().strip()
        if not token:
            return None
        certfile = os.getenv('RMON_SERVER_CLIENT_CERT_FILE')
        keyfile = os.getenv('RMON_SERVER_CLIENT_KEY_FILE')
        if bool(certfile) != bool(keyfile) or (certfile and parsed.scheme != 'https'):
            return None
        cert = (certfile, keyfile) if certfile else None
        with requests.Session() as session:
            session.trust_env = False
            with session.get(url + '/internal/version', headers={'Authorization': 'Bearer ' + token},
                             verify=os.getenv('RMON_SERVER_CA_FILE') or True, cert=cert,
                             timeout=(3, 3), allow_redirects=False) as response:
                if response.status_code != 200:
                    return None
                data = response.json()
                if isinstance(data, dict) and data.get('service') == 'rmon-server' and isinstance(data.get('version'), str):
                    return _valid_version(data['version'])
    except (OSError, KeyError, ValueError, requests.RequestException):
        pass
    return None


def update_cur_tool_version(tool_name: str) -> dict:
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', tool_name):
        raise ValueError('Invalid service name')
    if tool_name == 'rmon-server' and os.getenv('RMON_SERVER_INTERNAL_URL'):
        current = _server_runtime_version()
        roxy_sql.update_tool_cur_version(tool_name, current or '0')
        return {'current_version': current or '0', 'version_known': bool(current), 'installed': True, 'managed_by': 'docker'}
    if os.getenv('RMON_CONTAINER') == '1':
        return {'current_version': '0', 'version_known': False, 'installed': None, 'managed_by': 'external'}
    if distro.id() in ('ubuntu', 'debian') or 'debian' in distro.like().split():
        package = _version_command(['dpkg-query', '-W', '-f=${Status}\t${Version}', tool_name])
        version = package.split('\t', 1)[1] if package and package.startswith('install ok installed\t') else None
    else:
        version = _version_command(['rpm', '-q', '--queryformat', '%{VERSION}-%{RELEASE}', tool_name])
    # Preserve the package revision convention already used by the UI.
    current = _valid_version(version.split(':')[-1].replace('-', '.') if version else None)
    if not current and version:
        # Distribution suffixes (ubuntu1, el9, etc.) are package builds, not service versions.
        current = _valid_version(version.split(':')[-1].split('-', 1)[0])
    installed = True if current else None
    if not current:
        properties = _version_command(['systemctl', 'show', tool_name,
                                      '--property=LoadState', '--property=WorkingDirectory'])
        unit = dict(line.split('=', 1) for line in (properties or '').splitlines() if '=' in line)
        if unit.get('LoadState') == 'not-found':
            installed = False
        elif unit.get('LoadState') == 'loaded':
            installed = True
            if tool_name in ('rmon-server', 'rmon-socket') and unit.get('WorkingDirectory'):
                current = _source_version(unit['WorkingDirectory'])
    roxy_sql.update_tool_cur_version(tool_name, current or '0')
    return {'current_version': current or '0', 'version_known': bool(current), 'installed': installed}


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
