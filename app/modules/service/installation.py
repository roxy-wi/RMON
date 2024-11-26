import os
from packaging import version

import ansible
import ansible_runner

import app.modules.db.sql as sql
import app.modules.server.server as server_mod
import app.modules.roxywi.common as roxywi_common
from app.modules.server.ssh import return_ssh_keys_path


def run_ansible(inv: dict, server_ips: str, ansible_role: str) -> object:
	inventory_path = '/var/www/rmon/app/scripts/ansible/inventory'
	inventory = f'{inventory_path}/{ansible_role}.json'
	proxy = sql.get_setting('proxy')
	proxy_serv = ''
	tags = ''
	agent_pid = server_mod.start_ssh_agent()

	try:
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
		'ACTION_WARNINGS': "no",
		'LOCALHOST_WARNING': "no",
		'COMMAND_WARNINGS': "no",
		'AWX_DISPLAY': False,
		'SSH_AUTH_PID': agent_pid['pid'],
		'SSH_AUTH_SOCK': agent_pid['socket'],
		'ANSIBLE_PYTHON_INTERPRETER': '/usr/bin/python3'
	}
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
		with open(inventory, 'a') as invent:
			invent.write(str(inv))
	except Exception as e:
		server_mod.stop_ssh_agent(agent_pid)
		roxywi_common.handle_exceptions(e, 'RMON server', 'Cannot save inventory file')

	try:
		result = ansible_runner.run(**kwargs)
	except Exception as e:
		server_mod.stop_ssh_agent(agent_pid)
		roxywi_common.handle_exceptions(e, 'RMON server', 'Cannot run Ansible')

	try:
		server_mod.stop_ssh_agent(agent_pid)
	except Exception as e:
		roxywi_common.logging('RMON server', f'error: Cannot stop SSH agent {e}')

	os.remove(inventory)

	if result.rc != 0:
		raise Exception('Something wrong with installation, check <a href="/logs/internal?log_file=rmon.error.log" target="_blank" class="link">Apache logs</a> for details')

	return result.stats


def _install_ansible_collections():
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
				roxywi_common.handle_exceptions(e, 'Roxy-WI server',
												f'Cannot install as collection. {trouble_link}')
			else:
				if exit_code != 0:
					raise Exception(
						f'error: Ansible collection installation was not successful: {exit_code}. {trouble_link}')
