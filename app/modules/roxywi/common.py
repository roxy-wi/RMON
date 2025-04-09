import os
import sys
import traceback
import glob
import logging
from typing import Any
import socket

from flask import request, g
from flask_jwt_extended import get_jwt
from flask_jwt_extended import verify_jwt_in_request
from pythonjsonlogger.json import JsonFormatter

import app.modules.db.sql as sql
import app.modules.db.roxy as roxy_sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
import app.modules.db.history as history_sql
import app.modules.roxy_wi_tools as roxy_wi_tools
from app.modules.roxywi.exception import (RoxywiResourceNotFound, RoxywiCheckLimits, RoxywiGroupMismatch, RoxywiPermissionError,
										  RoxywiConflictError)
from app.modules.roxywi.class_models import ErrorResponse

get_config_var = roxy_wi_tools.GetConfigVar()


def get_user_group(**kwargs) -> int:
	user_group = ''

	try:
		verify_jwt_in_request()
		claims = get_jwt()
		user_group_id = claims['group']
		group = group_sql.get_group(user_group_id)
		if group.group_id == int(user_group_id):
			if kwargs.get('id'):
				user_group = group.group_id
			else:
				user_group = group.name
	except Exception as e:
		raise Exception(f'error: {e}')
	return user_group


def check_user_group_for_flask():
	verify_jwt_in_request()
	claims = get_jwt()
	user_id = claims['user_id']
	group_id = claims['group']

	if user_sql.check_user_group(user_id, group_id):
		return True
	else:
		logger('Has tried to actions in not his group', 'warning')
		return False


def check_user_group_for_socket(user_id: int, group_id: int) -> bool:
	if user_sql.check_user_group(user_id, group_id):
		return True
	else:
		logger('Has tried to actions in not his group', 'warning')
		return False


def check_is_server_in_group(server_ip: str) -> bool:
	group_id = get_user_group(id=1)
	servers = server_sql.select_servers(server=server_ip)
	for s in servers:
		if (s[2] == server_ip and int(s[3]) == int(group_id)) or group_id == 1:
			return True
		else:
			logger('Has tried to actions in not his group server ', 'warning')
	return False


def get_files(folder, file_format, server_ip=None) -> list:
	if file_format == 'log':
		file = []
	else:
		file = set()
	return_files = set()
	i = 0
	for files in sorted(glob.glob(os.path.join(folder, f'*.{file_format}*'))):
		if file_format == 'log':
			try:
				file += [(i, files.split('/')[4])]
			except Exception as e:
				print(e)
		else:
			file.add(files.split('/')[-1])
		i += 1
	files = file
	if file_format == 'cfg' or file_format == 'conf':
		for file in files:
			ip = file.split("-")
			if server_ip == ip[0]:
				return_files.add(file)
		return sorted(return_files, reverse=True)
	else:
		return file


def set_logger():
	try:
		logs_in_json = sql.get_setting('json_format')
	except Exception:
		logs_in_json = 1
	log_path = get_config_var.get_config_var('main', 'log_path')
	log_file = f"{log_path}/rmon.log"

	if logs_in_json:
		log_handler = logging.FileHandler(log_file)
		hostname = socket.gethostname()
		formatter = JsonFormatter(
			"%(asctime)s %(levelname)s %(message)s",
			rename_fields={"asctime": "timestamp", "levelname": "level"},
			defaults={"service_name": "rmon", "hostname": hostname}
		)
		log_handler.setFormatter(formatter)

		logger_s = logging.getLogger('rmon')
		logger_s.addHandler(log_handler)
		logger_s.setLevel(logging.INFO)

		if not os.path.exists(log_path):
			os.makedirs(log_path)

		return logger_s
	else:
		logging.basicConfig(filename=log_file, format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
		return logging


logger_setup = set_logger()
log_level = {
		'info': logger_setup.info,
		'warning': logger_setup.warning,
		'error': logger_setup.error,
	}


def logger(action: str, level: str = 'info', additional_extra: dict = None, **kwargs) -> None:
	verify_jwt_in_request()
	claims = get_jwt()
	user_id = claims['user_id']
	login = user_sql.get_user_id(user_id=user_id).username
	hostname = socket.gethostname()

	try:
		user_group = get_user_group()
	except Exception:
		user_group = ''

	try:
		ip = request.remote_addr
	except Exception:
		ip = ''
	extra = {'ip': ip, 'user': login, 'group': user_group}

	if additional_extra:
		extra.update(additional_extra)

	log_level[level](action, extra=extra)

	if kwargs.get('keep_history'):
		try:
			keep_action_history(kwargs.get('service'), action, hostname, login, ip)
		except Exception as e:
			log_level['error'](f'Cannot save history: {e}', extra=extra)


def logging_without_user(action: str, level: str = 'error', extra=None) -> None:
	log_level[level](action, extra=extra)


def keep_action_history(service: str, action: str, server_ip: str, login: str, user_ip: str):
	if login != '':
		user = user_sql.get_user_by_username(login)
		user_id = user.user_id
	else:
		user_id = 0
	if user_ip == '':
		user_ip = 'localhost'

	try:
		if service == 'server':
			server = server_sql.get_server_by_ip(server_ip=server_ip)
			server_id = server.server_id
			hostname = server.hostname
		else:
			server_id = None
			hostname = socket.gethostname()
		history_sql.insert_action_history(service, action, server_id, user_id, user_ip, server_ip, hostname)
	except Exception as e:
		logger(f'Cannot save a history: {e}', 'error')


def get_dick_permit(**kwargs):
	if not kwargs.get('group_id'):
		try:
			group_id = get_user_group(id=1)
		except Exception as e:
			return str(e)
	else:
		group_id = kwargs.pop('group_id')

	if check_user_group_for_flask():
		try:
			servers = server_sql.get_dick_permit(group_id, **kwargs)
		except Exception as e:
			raise Exception(e)
		else:
			return servers
	else:
		print('Atata!')


def get_users_params(**kwargs):
	verify_jwt_in_request()
	user_data = get_jwt()

	try:
		user_id = user_data['user_id']
		user = user_sql.get_user_id(user_id)
	except Exception:
		raise Exception('Cannot get user id')

	try:
		role = user_sql.get_role_id(user_id, user_data['group'])
	except Exception as e:
		raise Exception(f'error: Cannot get user role {e}')

	if kwargs.get('disable'):
		servers = get_dick_permit(disable=0)
	else:
		servers = get_dick_permit()

	user_params = {
		'user': user.username,
		'role': role,
		'servers': servers,
		'lang': get_user_lang_for_flask(),
		'user_id': user_id,
		'group_id': user_data['group']
	}

	return user_params


def get_user_lang_for_flask() -> str:
	try:
		user_lang = request.cookies.get('lang')
	except Exception:
		return 'en'

	if user_lang is None:
		user_lang = 'en'

	return user_lang


def return_user_status() -> dict:
	user_subscription = {}
	user_subscription.setdefault('user_status', roxy_sql.select_user_status())
	user_subscription.setdefault('user_plan', roxy_sql.select_user_plan())

	return user_subscription


def return_unsubscribed_user_status() -> dict:
	user_subscription = {'user_status': 0, 'user_plan': 0}

	return user_subscription


def return_user_subscription():
	try:
		user_subscription = return_user_status()
	except Exception as e:
		user_subscription = return_unsubscribed_user_status()
		logger(f'Cannot get a user plan: {e}', 'error')

	return user_subscription


def handle_exceptions(ex: Exception, message: str, **kwargs: Any) -> None:
	"""
	:param ex: The exception that was caught
	:param message: The error message to be logged and raised
	:param kwargs: Additional keyword arguments to be passed to the logging function
	:return: None

	"""
	logger(f'{message}: {ex}', 'error', **kwargs)
	raise Exception(f'error: {message}: {ex}')


def handle_json_exceptions(ex: Exception, message: str) -> dict:
	logger(f'{message}: {ex}', 'error')
	return ErrorResponse(error=f'{message}: {ex}').model_dump(mode='json')


def is_user_has_access_to_its_group(user_id: int) -> None:
	if not user_sql.check_user_group(user_id, g.user_params['group_id']) and g.user_params['role'] != 1:
		raise RoxywiGroupMismatch


def is_user_has_access_to_group(user_id: int, group_id: int) -> None:
	if not user_sql.check_user_group(user_id, group_id) and g.user_params['role'] != 1:
		raise RoxywiGroupMismatch


def handler_exceptions_for_json_data(ex: Exception, main_ex_mes: str) -> tuple[dict, int]:
	if isinstance(ex, KeyError):
		exc_type, exc_obj, exc_tb = sys.exc_info()
		file_name = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
		stk = traceback.extract_tb(exc_tb, 1)
		function_name = stk[0][2]
		return handle_json_exceptions(ex, f'Missing key in JSON data in function: {function_name} in file: {file_name}'), 500
	elif isinstance(ex, ValueError):
		return handle_json_exceptions(ex, 'Wrong type or missing value in JSON data'), 500
	elif isinstance(ex, RoxywiPermissionError):
		return handle_json_exceptions(ex, 'You cannot edit this resource'), 403
	elif isinstance(ex, RoxywiResourceNotFound):
		return handle_json_exceptions(ex, 'Resource not found'), 404
	elif isinstance(ex, RoxywiCheckLimits):
		return handle_json_exceptions(ex, 'Limit exceeded'), 409
	elif isinstance(ex, RoxywiConflictError):
		return handle_json_exceptions(ex, 'Conflict'), 429
	else:
		return handle_json_exceptions(ex, main_ex_mes), 500
