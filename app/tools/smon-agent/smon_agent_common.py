import logging

import configparser

logging.basicConfig(filename='/var/log/roxy-wi/smon-agent.log', format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)


def get_config_var(sec: str, var: str) -> str:
    path_config = "/etc/roxy-wi/smon-agent.cfg"
    config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    config.read(path_config)
    try:
        return config.get(sec, var)
    except configparser.Error as e:
        mess = f'error: Cannot get {var} in {sec}: {e}'
        logging.error(mess)
        raise Exception(mess)
