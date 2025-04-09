from datetime import datetime
import dateutil

from pytz import timezone

import app.modules.db.sql as sql


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


def return_proxy_dict() -> dict:
	proxy = sql.get_setting('proxy')
	proxy_dict = {}
	if proxy is not None and proxy != '' and proxy != 'None':
		proxy_dict = {"https": proxy, "http": proxy}
	return proxy_dict
