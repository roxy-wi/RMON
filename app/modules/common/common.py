import re
from datetime import datetime
import dateutil

from shlex import quote
from shutil import which
from pytz import timezone

import app.modules.db.sql as sql

error_mess = 'error: All fields must be completed'


def get_present_time():
	"""
	Returns the current time in UTC.

	:return: The current time in UTC.
	:rtype: datetime.datetime
	"""
	present = datetime.now(timezone('UTC'))
	formatted_present = present.strftime('%b %d %H:%M:%S %Y %Z')
	return datetime.strptime(formatted_present, '%b %d %H:%M:%S %Y %Z')


def _convert_to_time_zone(date: datetime) -> datetime:
	"""
	Convert a datetime object to the specified time zone.

	:param date: The datetime object to convert.
	:return: The converted datetime object.
	"""
	from_zone = dateutil.tz.gettz('UTC')
	time_zone = sql.get_setting('time_zone')
	to_zone = dateutil.tz.gettz(time_zone)
	utc = date.replace(tzinfo=from_zone)
	native = utc.astimezone(to_zone)
	return native


def get_time_zoned_date(date: datetime, fmt: str = None) -> str:
	"""
	Formats a given date and returns the formatted date in the specified or default format.

	:param date: The date to be formatted.
	:type date: datetime

	:param fmt: The format to use for the formatted date. If not provided, a default format will be used.
	:type fmt: str, optional

	:return: The formatted date.
	:rtype: str
	"""
	native = _convert_to_time_zone(date)
	date_format = '%Y-%m-%d %H:%M:%S'
	if fmt:
		return native.strftime(fmt)
	else:
		return native.strftime(date_format)


def checkAjaxInput(ajax_input: str, var_type=None, default=None):
	"""
	Checks if the provided `ajax_input` string contains any non-permitted characters and returns the modified string.

	:param ajax_input: The input string to be checked and modified.
	:param var_type: Cast to the desired type.
	:param default: If default_value, return it with the modified string.
	:return: The modified `ajax_input` string, or an empty string if the input was empty or contained non-permitted characters.
	"""
	if var_type:
		if default:
			return var_type(default)
		ajax_input = var_type(ajax_input)
	if default and not ajax_input:
		return default
	if not ajax_input:
		return ''
	pattern = re.compile('[&;|$`]')
	if pattern.search(ajax_input):
		raise ValueError('Error: Non-permitted characters detected')
	else:
		return quote(ajax_input.rstrip())


def check_is_service_folder(service_path: str) -> bool:
	"""
	Check if the given `service_path` contains the name of a service folder.

	:param service_path: The path of the folder to be checked.
	:return: True if the `service_path` contains the name of a service folder, False otherwise.
	"""
	service_names = ['nginx', 'haproxy', 'apache2', 'httpd', 'keepalived']

	return any(service in service_path for service in service_names) and '..' not in service_path


def return_nice_path(return_path: str, is_service=1) -> str:
	"""
	Formats the given return path to make it a nice path.

	:param return_path: The return path that needs to be formatted.
	:param is_service: A flag indicating whether the return path must contain the name of the service. Defaults to 1.
	:return: The formatted nice path.

	"""
	if not check_is_service_folder(return_path) and is_service:
		return 'error: The path must contain the name of the service. Check it in RMON settings'

	if return_path[-1] != '/':
		return_path += '/'

	return return_path


def get_key(item):
	return item[0]


def is_tool(name):
	is_tool_installed = which(name)

	return True if is_tool_installed is not None else False


def wrap_line(content: str, css_class: str = "line") -> str:
	"""
	Wraps the provided content into a div HTML element with the given CSS class.
	"""
	return f'<div class="{css_class}">{content}</div>'


def highlight_word(line: str, word: str) -> str:
	"""
	Highlights the word in the line by making it bold and colored red.
	"""
	return line.replace(word, f'<span style="color: red; font-weight: bold;">{word}</span>')


def sanitize_input_word(word: str) -> str:
	"""
	Sanitizes the input word by removing certain characters.
	"""
	return re.sub(r'[?|$|!|^|*|\]|\[|,| |]', r'', word)


def return_proxy_dict() -> dict:
	proxy = sql.get_setting('proxy')
	proxy_dict = {}
	if proxy is not None and proxy != '' and proxy != 'None':
		proxy_dict = {"https": proxy, "http": proxy}
	return proxy_dict
