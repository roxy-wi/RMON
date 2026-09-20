import os
import json
import uuid
import subprocess
from pathlib import Path
from datetime import datetime
from packaging import version

import app.modules.db.sql as sql
import app.modules.db.server as server_sql
import app.modules.server.server as server_mod
import app.modules.roxywi.common as roxywi_common
from app.modules.server.ssh import return_ssh_keys_path
from app.modules.db.db_model import InstallationTasks


def run_ansible(inv: dict, server_ips: list, ansible_role: str, *, cancel_callback=None) -> dict:
    import ansible_runner
    import logging

    def check_cancelled():
        if cancel_callback and cancel_callback():
            raise RuntimeError('Agent operation was interrupted')

    check_cancelled()
    collection_path = _ensure_agent_collections() if ansible_role == 'rmon_agent' else None
    if collection_path is None:
        _install_ansible_collections()
    proxy = sql.get_setting('proxy')
    proxy_serv = proxy if proxy and proxy != 'None' else ''
    inventory_path = Path('/var/www/rmon/app/scripts/ansible/inventory')
    inventory = inventory_path / f'{ansible_role}-{uuid.uuid4().hex}.json'
    agent_pid = server_mod.start_ssh_agent()
    tags = ''
    try:
        for server_ip in server_ips:
            check_cancelled()
            ssh_settings = return_ssh_keys_path(server_ip)
            host = inv['server']['hosts'][server_ip]
            if ssh_settings['enabled']:
                host['ansible_ssh_private_key_file'] = ssh_settings['key']
                server_mod.add_key_to_agent(ssh_settings, agent_pid)
            host.update(ansible_password=ssh_settings['password'], ansible_user=ssh_settings['user'],
                        ansible_port=ssh_settings['port'], ansible_become=True, ansible_connection='ssh',
                        PROXY=proxy_serv)
            if 'DOCKER' in host:
                tags = 'docker' if host['DOCKER'] else 'system'
        envvars = {
            'ANSIBLE_DISPLAY_OK_HOSTS': 'no', 'ANSIBLE_SHOW_CUSTOM_STATS': 'no',
            'ANSIBLE_DISPLAY_SKIPPED_HOSTS': 'no', 'ANSIBLE_DEPRECATION_WARNINGS': 'no',
            'ANSIBLE_HOST_KEY_CHECKING': 'no', 'ANSIBLE_TIMEOUT': 15,
            'ACTION_WARNINGS': 'no', 'LOCALHOST_WARNING': 'no', 'COMMAND_WARNINGS': 'no',
            'AWX_DISPLAY': False, 'SSH_AUTH_PID': agent_pid['pid'], 'SSH_AUTH_SOCK': agent_pid['socket'],
            'ANSIBLE_PYTHON_INTERPRETER': '/usr/bin/python3',
        }
        if collection_path:
            envvars['ANSIBLE_COLLECTIONS_PATH'] = collection_path
        if os.getenv('RMON_CONTAINER') == '1':
            envvars.update(ANSIBLE_HOME='/tmp/ansible-local', ANSIBLE_SSH_CONTROL_PATH_DIR='/tmp/ansible-local/cp')
        kwargs = {
            'private_data_dir': '/var/www/rmon/app/scripts/ansible/',
            'inventory': str(inventory), 'envvars': envvars,
            'playbook': f'/var/www/rmon/app/scripts/ansible/roles/{ansible_role}.yml', 'tags': tags,
        }
        if cancel_callback is not None:
            kwargs['cancel_callback'] = cancel_callback
        check_cancelled()
        inventory_path.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(inventory, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(inv, stream)
        result = ansible_runner.run(**kwargs)
        check_cancelled()
        if result.rc != 0:
            raise RuntimeError('Agent operation failed. Check SSH access and the failed task in the operations service logs.')
        return result.stats
    finally:
        try:
            inventory.unlink(missing_ok=True)
        finally:
            try:
                server_mod.stop_ssh_agent(agent_pid)
            except Exception as error:
                logging.getLogger(__name__).error('Cannot stop operation SSH agent (%s)', type(error).__name__)


def _ensure_agent_collections() -> str:
	if os.getenv('RMON_CONTAINER') == '1':
		root = Path('/usr/share/ansible/collections')
	else:
		from app.modules.roxy_wi_tools import GetConfigVar
		root = Path(GetConfigVar().get_config_var('main', 'lib_path')) / 'ansible/collections'
	required = ('docker', 'general', 'crypto')
	if not all((root / 'ansible_collections/community' / name).is_dir() for name in required):
		if os.getenv('RMON_CONTAINER') == '1':
			raise RuntimeError('Required Ansible collections are missing from this RMON installation')
		root.mkdir(parents=True, exist_ok=True)
		manifest = Path(__file__).resolve().parents[2] / 'scripts/ansible/requirements.yml'
		subprocess.run(['ansible-galaxy', 'collection', 'install', '-r', str(manifest), '-p', str(root)],
		               check=True, capture_output=True, text=True, timeout=180)
	return str(root)


def _install_ansible_collections():
	if os.getenv('RMON_CONTAINER') == '1':
		return
	import ansible

	old_ansible_server = ''
	collections = ('community.general', 'ansible.posix', 'community.docker')
	trouble_link = 'Read <a href="https://rmon.op/troubleshooting#ansible_collection" target="_blank" class="link">troubleshooting</a>'
	for collection in collections:
		if not os.path.isdir(
				f'/usr/share/httpd/.ansible/collections/ansible_collections/{collection.replace(".", "/")}'):
			try:
				if version.parse(ansible.__version__) < version.parse('2.13.9'):
					old_ansible_server = '--server https://old-galaxy.ansible.com/'
				exit_code = os.system(f'ansible-galaxy collection install {collection} {old_ansible_server}')
			except Exception as e:
				roxywi_common.handle_exceptions(e, f'Cannot install as collection. {trouble_link}')
			else:
				if exit_code != 0:
					raise Exception(
						f'error: Ansible collection installation was not successful: {exit_code}. {trouble_link}')


def run_ansible_thread(inv: dict, server_ips: list, ansible_role: str, service_name: str, action: str) -> int:
	# Keep the existing caller contract; execution now belongs to the operations service.
	from app.modules.operations.queue import enqueue
	claims = roxywi_common.get_jwt_token_claims()
	return enqueue(inv, server_ips, ansible_role, service_name, action, claims['user_id'])


def execute_installation(inv, server_ips, service, *, cancel_callback=None):
	kwargs = {'cancel_callback': cancel_callback} if cancel_callback else {}
	output = run_ansible(inv, server_ips, service, **kwargs)
	if output.get('failures') or output.get('dark'):
		raise RuntimeError('Agent operation failed. Check SSH access and the failed task in the operations service logs.')
	if cancel_callback and cancel_callback():
		raise RuntimeError('Agent operation was interrupted')


def run_installations(inv: dict, server_ips: list, service: str, task_id: int) -> None:
	try:
		InstallationTasks.update(status='running').where(InstallationTasks.id == task_id).execute()
		execute_installation(inv, server_ips, service)
		if service == 'rmon_agent':
			from app.modules.common.agent_transport import record_applied
			record_applied(inv)
		InstallationTasks.update(status='completed', finish_date=datetime.now()).where(InstallationTasks.id == task_id).execute()
	except Exception as e:
		InstallationTasks.update(status='failed', finish_date=datetime.now(), error=str(e)).where(InstallationTasks.id == task_id).execute()
		roxywi_common.logging_without_user(f'Cannot install {service}: {e}', 'error', extra={'task_id': task_id})
