import os
import json
import uuid
import threading
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


def run_ansible(inv: dict, server_ips: list, ansible_role: str) -> dict:
	import ansible_runner

	inventory_path = '/var/www/rmon/app/scripts/ansible/inventory'
	inventory = f'{inventory_path}/{ansible_role}-{uuid.uuid4().hex}.json'
	proxy = sql.get_setting('proxy')
	proxy_serv = ''
	tags = ''
	agent_pid = server_mod.start_ssh_agent()

	try:
		if ansible_role == 'rmon_agent':
			collection_path = _ensure_agent_collections()
		else:
			_install_ansible_collections()
	except Exception as e:
		raise Exception(f'{e}')

	for server_ip in server_ips:
		ssh_settings = return_ssh_keys_path(server_ip)
		if ssh_settings['enabled']:
			inv['server']['hosts'][server_ip]['ansible_ssh_private_key_file'] = ssh_settings['key']
		inv['server']['hosts'][server_ip]['ansible_password'] = ssh_settings['password']
		inv['server']['hosts'][server_ip]['ansible_user'] = ssh_settings['user']
		inv['server']['hosts'][server_ip]['ansible_port'] = ssh_settings['port']
		inv['server']['hosts'][server_ip]['ansible_become'] = True
		inv['server']['hosts'][server_ip]['ansible_connection'] = 'ssh'

		if ssh_settings['enabled']:
			try:
				server_mod.add_key_to_agent(ssh_settings, agent_pid)
			except Exception as e:
				server_mod.stop_ssh_agent(agent_pid)
				raise Exception(e)

		if proxy is not None and proxy != '' and proxy != 'None':
			proxy_serv = proxy

		inv['server']['hosts'][server_ip]['PROXY'] = proxy_serv

		if 'DOCKER' in inv['server']['hosts'][server_ip]:
			if inv['server']['hosts'][server_ip]['DOCKER']:
				tags = 'docker'
			else:
				tags = 'system'

	envvars = {
		'ANSIBLE_DISPLAY_OK_HOSTS': 'no',
		'ANSIBLE_SHOW_CUSTOM_STATS': 'no',
		'ANSIBLE_DISPLAY_SKIPPED_HOSTS': "no",
		'ANSIBLE_DEPRECATION_WARNINGS': "no",
		'ANSIBLE_HOST_KEY_CHECKING': "no",
		'ANSIBLE_TIMEOUT': 15,
		'ACTION_WARNINGS': "no",
		'LOCALHOST_WARNING': "no",
		'COMMAND_WARNINGS': "no",
		'AWX_DISPLAY': False,
		'SSH_AUTH_PID': agent_pid['pid'],
		'SSH_AUTH_SOCK': agent_pid['socket'],
		'ANSIBLE_PYTHON_INTERPRETER': '/usr/bin/python3'
	}
	if ansible_role == 'rmon_agent':
		envvars['ANSIBLE_COLLECTIONS_PATH'] = collection_path
	if os.getenv('RMON_CONTAINER') == '1':
		envvars['ANSIBLE_HOME'] = '/tmp/ansible-local'
		envvars['ANSIBLE_SSH_CONTROL_PATH_DIR'] = '/tmp/ansible-local/cp'
	kwargs = {
		'private_data_dir': '/var/www/rmon/app/scripts/ansible/',
		'inventory': inventory,
		'envvars': envvars,
		'playbook': f'/var/www/rmon/app/scripts/ansible/roles/{ansible_role}.yml',
		'tags': tags
	}

	if os.path.isfile(inventory):
		os.remove(inventory)

	if not os.path.isdir(inventory_path):
		os.makedirs(inventory_path)

	try:
		descriptor = os.open(inventory, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
		with os.fdopen(descriptor, 'w') as invent:
			json.dump(inv, invent)
	except Exception as e:
		server_mod.stop_ssh_agent(agent_pid)
		roxywi_common.handle_exceptions(e, 'Cannot save inventory file')

	try:
		result = ansible_runner.run(**kwargs)
	except Exception as e:
		server_mod.stop_ssh_agent(agent_pid)
		roxywi_common.handle_exceptions(e, 'Cannot run Ansible')

	try:
		server_mod.stop_ssh_agent(agent_pid)
	except Exception as e:
		roxywi_common.logger(f'Cannot stop SSH agent {e}', 'error')

	os.remove(inventory)

	if result.rc != 0:
		raise Exception('Agent operation failed. Check SSH access and the failed task in the RMON web service logs.')

	return result.stats


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
	claims = roxywi_common.get_jwt_token_claims()
	server_id = server_sql.get_server_by_ip(server_ips[0]).server_id

	task_id = InstallationTasks.insert(
		service_name=service_name, server_id=server_id, user_id=claims['user_id'], group_id=claims['group'], action=action
	).execute()
	thread = threading.Thread(target=run_installations, args=(inv, server_ips, ansible_role, task_id))
	thread.start()
	return task_id


def run_installations(inv: dict, server_ips: list, service: str, task_id: int) -> None:
	try:
		InstallationTasks.update(status='running').where(InstallationTasks.id == task_id).execute()
		output = run_ansible(inv, server_ips, service)
		if len(output['failures']) > 0 or len(output['dark']) > 0:
			InstallationTasks.update(
				status='failed', finish_date=datetime.now(), error=f'Cannot install {service}. Check Apache error log'
			).where(InstallationTasks.id == task_id).execute()
			return
		if service == 'rmon_agent':
			from app.modules.common.agent_transport import record_applied
			record_applied(inv)
		InstallationTasks.update(status='completed', finish_date=datetime.now()).where(InstallationTasks.id == task_id).execute()
	except Exception as e:
		InstallationTasks.update(status='failed', finish_date=datetime.now(), error=str(e)).where(InstallationTasks.id == task_id).execute()
		roxywi_common.logging_without_user(f'Cannot install {service}: {e}', 'error', extra={'task_id': task_id})
