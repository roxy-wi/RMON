"""Minimal HTTP server used by the application startup smoke test."""

import os

from werkzeug.serving import make_server

from app import app


if __name__ == '__main__':
    port = int(os.environ['RMON_SMOKE_PORT'])
    server = make_server('127.0.0.1', port, app)
    print(f'RMON smoke server listening on {port}', flush=True)
    server.serve_forever()
