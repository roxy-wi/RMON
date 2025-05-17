import logging
import os
import socket

from pythonjsonlogger.json import JsonFormatter

from app.modules.db import sql as sql
import app.modules.roxy_wi_tools as roxy_wi_tools

get_config_var = roxy_wi_tools.GetConfigVar()


def set_logger():
    try:
        logs_in_json = sql.get_setting('json_format')
    except Exception:
        logs_in_json = 1
    log_path = get_config_var.get_config_var('main', 'log_path')
    log_file = f"{log_path}/rmon.log"

    if logs_in_json:
        log_data = {}
        log_handler = logging.FileHandler(log_file)
        hostname = socket.gethostname()
        # Add request context if available

        formatter = JsonFormatter(
            "%(asctime)s %(levelname)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
            defaults={"service_name": "rmon", "hostname": hostname, **log_data},
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
