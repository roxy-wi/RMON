import os
import glob
from typing import Any
import socket

from flask import request, g, has_request_context, abort
from flask_jwt_extended import get_jwt
from flask_jwt_extended import verify_jwt_in_request

import app.modules.db.roxy as roxy_sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
import app.modules.db.history as history_sql
import app.modules.roxy_wi_tools as roxy_wi_tools
from app.modules.roxywi.exception import RoxywiGroupMismatch
from app.modules.roxywi.class_models import ErrorResponse
from app.modules.roxywi.error_handler import handle_exception
from app.modules.roxywi.logger import log_level

get_config_var = roxy_wi_tools.GetConfigVar()


def get_jwt_token_claims() -> dict:
	verify_jwt_in_request()
	claims = get_jwt()
	claim = {'user_id': claims['user_id'], 'group': claims['group']}
	return claim


def get_user_group(**kwargs) -> int:
	user_group = ''

	try:
		claims = get_jwt_token_claims()
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
	claims = get_jwt_token_claims()
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
	server = server_sql.get_server_by_ip(server_ip)
	if server.ip == server_ip and int(server.group_id) == int(group_id):
		return True
	logger('Has tried to actions in not his group server ', 'warning')
	abort(403, 'You have no access to this server')


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


def logger(action: str, level: str = 'info', additional_extra: dict = None, **kwargs) -> None:
	claims = get_jwt_token_claims()
	user_id = claims['user_id']
	login = user_sql.get_user_id(user_id=user_id).username
	hostname = socket.gethostname()
	ip = ""
	extra = {}

	try:
		user_group = get_user_group()
	except Exception:
		user_group = ''

	if has_request_context():
		extra['request'] = {
			'method': request.method,
			'path': request.path,
			'ip': request.remote_addr,
		}
		ip = request.remote_addr

	extra.update({'ip': ip, 'user': login, 'group': user_group})

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
	user_data = get_jwt_token_claims()

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


def is_user_has_access_to_its_group(user_id: int) -> None:
	if not user_sql.check_user_group(user_id, g.user_params['group_id']) and g.user_params['role'] != 1:
		raise RoxywiGroupMismatch


def is_user_has_access_to_group(user_id: int, group_id: int) -> None:
	if not user_sql.check_user_group(user_id, group_id) and g.user_params['role'] != 1:
		raise RoxywiGroupMismatch


def require_active_group_access(group_id: int) -> None:
	"""Require a resource to belong to the group selected in the current token."""
	if str(g.user_params.get('role', '')) == '1':
		return
	if int(group_id) != int(g.user_params['group_id']):
		raise RoxywiGroupMismatch


def get_visible_groups():
	"""Return every group for role 1 and memberships only for other roles."""
	if int(g.user_params['role']) == 1:
		return group_sql.select_groups()
	return group_sql.select_groups_for_user(g.user_params['user_id'])


def require_request_server_access() -> None:
	"""Authorize every managed-server reference used by a legacy endpoint."""
	view_args = request.view_args or {}
	references = [(key, view_args[key]) for key in ('server_id', 'server_ip') if view_args.get(key) is not None]
	request_data = request.get_json(silent=True) or request.form
	if not hasattr(request_data, 'get'):
		request_data = {}
	for key in ('server_id', 'server_ip', 'serv'):
		if request_data.get(key) is not None:
			references.append((key, request_data.get(key)))

	if not references:
		return

	try:
		resolved_server_ids = set()
		for key, server_reference in references:
			if server_reference in ('', None, 'all'):
				continue
			if key == 'server_id' and (isinstance(server_reference, int) or str(server_reference).isdigit()):
				server = server_sql.get_server(int(server_reference))
			else:
				server = server_sql.get_server_by_ip(str(server_reference))
			require_active_group_access(server.group_id)
			resolved_server_ids.add(server.server_id)
		if len(resolved_server_ids) > 1:
			raise PermissionError('Server ID and IP refer to different servers')
	except Exception:
		abort(403, 'Server does not belong to the active group')


def handle_json_exceptions(ex: Exception, message: str) -> dict:
	"""
	Handle an exception and return a JSON error response.

	Args:
		ex: The exception that was raised
		message: Additional information to include in the response

	Returns:
		A dictionary containing the error response
	"""
	logger('{message}: {ex}', 'error')
	return ErrorResponse(error=f'{message}: {ex}').model_dump(mode='json')


def handler_exceptions_for_json_data(ex: Exception, main_ex_mes: str = '') -> tuple[dict, int]:
	"""
	Handle an exception and return a JSON error response with an appropriate HTTP status code.

	Args:
		ex: The exception that was raised
		main_ex_mes: Additional information to include in the response

	Returns:
		A tuple containing the error response and HTTP status code
	"""

	# If main_ex_mes is provided, use it as additional_info
	additional_info = main_ex_mes if main_ex_mes else ""

	# Use the centralized error handler
	return handle_exception(ex, additional_info=additional_info)
