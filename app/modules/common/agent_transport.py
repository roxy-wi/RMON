"""Group-owned settings for agent result delivery."""
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

MODES = ('http', 'https', 'mtls')
DEFAULTS = {
    'agent_result_transport': 'http',
    'agent_tls_ca_file': '',
    'agent_tls_generate': '1',
    'agent_tls_ca_key_file': '',
    'agent_tls_cert_file': '',
    'agent_tls_key_file': '',
}
PATH_SETTINGS = frozenset(DEFAULTS) - {'agent_result_transport', 'agent_tls_generate'}


def setting_rows(group_id):
    return [dict(param=key, value=value, section='agent', desc='', group_id=group_id)
            for key, value in DEFAULTS.items()]


def group_settings(group_id):
    from app.modules.db.db_model import Setting
    values = dict(DEFAULTS)
    values.update({row.param: row.value or '' for row in Setting.select().where(
        (Setting.group_id == int(group_id)) & (Setting.param.in_(tuple(DEFAULTS))))})
    return values


def certificate_root(group_id):
    # Only host configuration can select the base; group admins cannot change it.
    base = Path(os.getenv('RMON_AGENT_CERTIFICATES_DIR', '/var/lib/rmon/keys/agent-certificates'))
    base = base.resolve()
    root = base / str(int(group_id))
    if not root.resolve().is_relative_to(base) or root.is_symlink():
        raise ValueError('The group certificate directory is invalid')
    return root


def certificate_path(value, group_id, agent_uuid=None, *, require_file=False):
    if not value:
        return ''
    if any(char in value for char in ('\n', '\r', '\x00', ',', '\\')):
        raise ValueError('Invalid certificate path')
    if '{' in value or '}' in value:
        if value.replace('{uuid}', '').find('{') != -1 or '}' in value.replace('{uuid}', ''):
            raise ValueError('Only {uuid} is supported in certificate paths')
        value = value.replace('{uuid}', str(UUID(str(agent_uuid))) if agent_uuid else 'agent-id')
    root = certificate_root(group_id)
    path = Path(value)
    if not path.is_absolute() or not path.resolve().is_relative_to(root):
        raise ValueError(f'Certificate files must be inside {root.as_posix()}')
    if require_file and (not path.is_file() or not os.access(path, os.R_OK)):
        raise ValueError('A configured certificate file is missing or cannot be read')
    return path.resolve().as_posix()


def validate_setting(param, value, group_id):
    if param not in DEFAULTS:
        raise ValueError('Unknown agent connection setting')
    value = value.strip()
    if param == 'agent_result_transport' and value not in MODES:
        raise ValueError('Select HTTP, HTTPS or HTTPS + mTLS')
    if param == 'agent_tls_generate' and value not in ('0', '1'):
        raise ValueError('Certificate generation must be enabled or disabled')
    if param in PATH_SETTINGS:
        if '{uuid}' in value and param not in ('agent_tls_cert_file', 'agent_tls_key_file'):
            raise ValueError('The CA path cannot contain {uuid}')
        certificate_path(value, group_id)
    return value


def settings_hash(values, mode):
    # A new group default does not reconfigure agents that already chose a mode.
    keys = set()
    if mode == 'mtls':
        keys = PATH_SETTINGS | {'agent_tls_generate'}
    elif mode == 'https':
        keys = {'agent_tls_ca_file'}
    data = {key: values[key] for key in sorted(keys)}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def inventory_settings(group_id, agent_uuid, mode):
    if mode not in MODES:
        raise ValueError('Select HTTP, HTTPS or HTTPS + mTLS')
    values = group_settings(group_id)
    validate_setting('agent_tls_generate', values['agent_tls_generate'], group_id)
    result = dict(agent_transport=mode, agent_mtls_enabled=mode == 'mtls',
                  agent_tls_generate=values['agent_tls_generate'] == '1',
                  agent_verify_result_connection=True,
                  agent_transport_settings_hash=settings_hash(values, mode),
                  agent_certificate_directory=certificate_root(group_id).as_posix())
    for key in PATH_SETTINGS:
        result[key] = ''
        if mode == 'http' or (mode == 'https' and key != 'agent_tls_ca_file'):
            continue
        value = values[key]
        validate_setting(key, value, group_id)
        result[key] = certificate_path(value, group_id, agent_uuid, require_file=True)
    if mode == 'mtls':
        if not result['agent_tls_ca_file']:
            raise ValueError('Select the trusted CA certificate in the agent group settings')
        if bool(result['agent_tls_cert_file']) != bool(result['agent_tls_key_file']):
            raise ValueError('Specify both the client certificate and its private key')
    return result


def pending(agent):
    mode = agent.result_transport
    if not mode:
        return False
    return (mode != agent.applied_result_transport or
            (mode != 'http' and agent.transport_settings_hash !=
             settings_hash(group_settings(agent.server_id.group_id), mode)))


def record_applied(inventory):
    from datetime import datetime
    from app.modules.db.db_model import SmonAgent
    for host in inventory.get('server', {}).get('hosts', {}).values():
        if host.get('agent_verify_result_connection') and host.get('action') == 'install':
            SmonAgent.update(
                applied_result_transport=host['agent_transport'],
                transport_settings_hash=host['agent_transport_settings_hash'],
                transport_checked_at=datetime.now(),
            ).where(SmonAgent.uuid == str(host['agent_uuid'])).execute()
