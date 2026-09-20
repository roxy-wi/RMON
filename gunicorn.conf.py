"""Shared package/container worker policy. TLS belongs to Apache or Nginx."""
import os

os.environ['RMON_SCHEDULER_ENABLED'] = '0'

container = os.getenv('RMON_CONTAINER') == '1'
bind = '0.0.0.0:8080' if container else 'unix:/run/rmon/rmon.sock'
workers = 1
worker_class = 'gthread'
threads = 10
preload_app = False
max_requests = 0
timeout = 120
graceful_timeout = 30
keepalive = 5
umask = 0o007
chdir = '/var/www/rmon'
worker_tmp_dir = '/tmp'
accesslog = '-'
errorlog = '-'
capture_output = True
limit_request_line = 8190
# Compose exposes only Nginx; the package uses an Apache-only Unix socket.
# Both proxies replace the incoming scheme header. Do not publish port 8080.
forwarded_allow_ips = '*' if container else ''
secure_scheme_headers = {'X-FORWARDED-PROTO': 'https'}
if container:
    user = 'www-data'
    group = 'www-data'
