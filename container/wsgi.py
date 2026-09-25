"""Gunicorn target; private readiness probe without exposing a Flask route."""
import hmac
import os

from app import app
from app.modules.db.db_model import Setting, conn


def application(environ, start_response):
    if environ.get('PATH_INFO') != '/_rmon/ready':
        return app(environ, start_response)
    token = os.getenv('RMON_HEALTH_TOKEN', '')
    supplied = environ.get('HTTP_X_RMON_HEALTH_TOKEN', '')
    if not token or not hmac.compare_digest(token.encode(), supplied.encode()):
        status, body = '404 Not Found', b'Not found'
    else:
        try:
            with app.app_context(), conn.connection_context():
                if not Setting.select().limit(1).exists():
                    raise RuntimeError('Uninitialized database')
            status, body = '200 OK', b'{"status":"ready"}'
        except Exception:
            status, body = '503 Service Unavailable', b'{"status":"not_ready"}'
    start_response(status, [('Content-Type', 'application/json'), ('Content-Length', str(len(body)))])
    return [body]
