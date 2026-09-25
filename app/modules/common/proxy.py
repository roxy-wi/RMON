"""Only enabled by deployments where the Gunicorn backend is private."""
import os

from werkzeug.middleware.proxy_fix import ProxyFix


def configure_trusted_proxy(app):
    if os.getenv('RMON_PROXY_MODE') == '1':
        # Nginx replaces XFF; Apache appends the actual client as the last hop.
        # Gunicorn handles the trusted scheme header. Never trust forwarded Host.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=0, x_host=0, x_port=0, x_prefix=0)
