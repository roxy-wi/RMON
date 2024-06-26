import os
import re

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import app.modules.db.sql as sql
import app.modules.db.roxy as roxy_sql
import app.modules.common.common as common
import app.modules.roxywi.common as roxywi_common
import app.modules.server.server as server_mod


def is_docker() -> bool:
	path = "/proc/self/cgroup"
	if not os.path.isfile(path):
		return False
	with open(path) as f:
		for line in f:
			if re.match("\d+:[\w=]+:/docker(-[ce]e)?/\w+", line):
				return True
	return_out = server_mod.subprocess_execute_with_rc('systemctl status rsyslog')
	if return_out['rc']:
		return True
	return False


def check_ver():
	return roxy_sql.get_ver()


def versions():
	try:
		current_ver = check_ver()
		current_ver_without_dots = current_ver.split('.')
		current_ver_without_dots = ''.join(current_ver_without_dots)
		current_ver_without_dots = current_ver_without_dots.replace('\n', '')
		current_ver_without_dots = int(current_ver_without_dots)
	except Exception:
		current_ver = "Cannot get current version"
		current_ver_without_dots = 0

	try:
		new_ver = check_new_version('rmon')
		new_ver_without_dots = new_ver.split('.')
		new_ver_without_dots = ''.join(new_ver_without_dots)
		new_ver_without_dots = new_ver_without_dots.replace('\n', '')
		new_ver_without_dots = int(new_ver_without_dots)
	except Exception as e:
		new_ver = "Cannot get a new version"
		new_ver_without_dots = 0
		roxywi_common.logging('RMON server', f' {e}')

	return current_ver, new_ver, current_ver_without_dots, new_ver_without_dots


def check_new_version(service):
	current_ver = check_ver()
	res = ''
	proxy_dict = common.return_proxy_dict()

	try:
		response = requests.get(f'https://rmon.io/version/get/{service}', timeout=1, proxies=proxy_dict)
		if service == 'rmon':
			requests.get(f'https://rmon.io/version/send/{current_ver}', timeout=1, proxies=proxy_dict)

		res = response.content.decode(encoding='UTF-8')
	except requests.exceptions.RequestException as e:
		roxywi_common.logging('RMON server', f' {e}')

	return res


def update_user_status() -> None:
	user_license = sql.get_setting('license')
	proxy_dict = common.return_proxy_dict()
	retry_strategy = Retry(
		total=3,
		status_forcelist=[429, 500, 502, 503, 504]
	)
	adapter = HTTPAdapter(max_retries=retry_strategy)
	roxy_wi_get_plan = requests.Session()
	roxy_wi_get_plan.mount("https://", adapter)
	json_body = {'license': user_license}
	roxy_wi_get_plan = requests.post('https://rmon.io/user/license', timeout=5, proxies=proxy_dict, json=json_body)
	try:
		status = roxy_wi_get_plan.json()
		roxy_sql.update_user_status(status['status'], status['plan'], status['method'])
	except Exception as e:
		roxywi_common.logging('RMON server', f'error: Cannot get user status {e}')


def action_service(action: str, service: str) -> str:
	is_in_docker = is_docker()
	cmd = f"sudo systemctl disable {service} --now"
	if action in ("start", "restart"):
		cmd = f"sudo systemctl {action} {service} --now"
	if is_in_docker:
		cmd = f"sudo supervisorctl {action} {service}"
	os.system(cmd)
	roxywi_common.logging('RMON server', f' The service {service} has been {action}ed', login=1)
	return 'ok'


def update_plan():
	if roxy_sql.select_user_name():
		roxy_sql.update_user_name('user')
	else:
		roxy_sql.insert_user_name('user')
	update_user_status()
