from datetime import datetime
import dateutil
import functools
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar
import time

from pytz import timezone

import app.modules.db.sql as sql

# Type variable for generic function return type
T = TypeVar('T')

# Cache for storing query results
_query_cache: Dict[str, Tuple[Any, float]] = {}
# Default cache expiration time in seconds (5 minutes)
DEFAULT_CACHE_EXPIRY = 300


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


def cached_query(expiry: Optional[int] = None) -> Callable[[Callable[..., T]], Callable[..., T]]:
	"""
	Decorator for caching database query results.

	:param expiry: Cache expiration time in seconds. If None, uses DEFAULT_CACHE_EXPIRY.
	:return: Decorated function that caches results.
	"""
	def decorator(func: Callable[..., T]) -> Callable[..., T]:
		@functools.wraps(func)
		def wrapper(*args, **kwargs) -> T:
			# Create a cache key based on function name and arguments
			cache_key = f"{func.__module__}.{func.__name__}:{str(args)}:{str(kwargs)}"

			# Check if result is in cache and not expired
			if cache_key in _query_cache:
				result, timestamp = _query_cache[cache_key]
				cache_expiry = expiry if expiry is not None else DEFAULT_CACHE_EXPIRY
				if time.time() - timestamp < cache_expiry:
					return result

			# Execute the function and cache the result
			result = func(*args, **kwargs)
			_query_cache[cache_key] = (result, time.time())
			return result
		return wrapper
	return decorator


def clear_cache() -> None:
	"""
	Clear the entire query cache.
	"""
	_query_cache.clear()


def clear_cache_for_function(func_name: str) -> None:
	"""
	Clear cache entries for a specific function.

	:param func_name: The name of the function to clear cache for.
	"""
	keys_to_remove = [key for key in _query_cache if key.startswith(func_name)]
	for key in keys_to_remove:
		del _query_cache[key]
