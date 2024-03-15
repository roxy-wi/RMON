import json
import time
import socket
import logging
from datetime import datetime
import subprocess
from contextlib import closing

from retry import retry
from pytz import timezone
import dns.resolver
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib3
from urllib.request import ssl
from urllib.request import socket as url_socket

import smon_agent_common as common

logging.basicConfig(filename='/var/log/rmon/rmon-agent.log', format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)
urllib3.disable_warnings()


def get_agent_headers() -> dict:
    agent_uuid = common.get_config_var('agent', 'uuid')
    return {'Agent-UUID': str(agent_uuid)}


@retry(delay=5, tries=6)
def send_result_to_master(json_data) -> None:
    master_ip = common.get_config_var('master', 'host')
    master_port = common.get_config_var('master', 'port')
    headers = get_agent_headers()

    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    send_check_data = requests.Session()
    send_check_data.mount("http://", adapter)
    send_check_data = requests.post(f'http://{master_ip}:{master_port}/agent/check/result', timeout=5, json=json_data, headers=headers, verify=False)
    try:
        status = send_check_data.content.decode(encoding='UTF-8')
        status = status.split(' ')
        logging.info(f'Check result has been sent to master: {status} {json_data}')
    except Exception as e:
        logging.error(f'error: Cannot send check result: {json_data}: {e}')


def get_time() -> json:
    return json.dumps(datetime.now(timezone('UTC')), sort_keys=True, default=str)


def check_ping(**kwargs):
    try:
        check = SmonPing(kwargs.get('check_id'), kwargs.get('server_ip'), kwargs.get('packet_size'))
        check.check_ping()
        logging.info('Ping check started')
    except Exception as e:
        logging.error(f'Cannot start Ping check {e}')


def check_dns(**kwargs):
    try:
        check = SmonDns(kwargs.get('check_id'), kwargs.get('resolver'), kwargs.get('record_type'), kwargs.get('server_ip'))
        check.check_dns()
        logging.info('DNS check started')
    except Exception as e:
        logging.error(f'Cannot start DNS check {e}')


def check_tcp(**kwargs):
    try:
        check = SmonTcp(kwargs.get('check_id'), kwargs.get('server_ip'), kwargs.get('port'))
        check.check_tcp()
        logging.info('TCP check started')
    except Exception as e:
        logging.error(f'Cannot start TCP check {e}')


def check_http(**kwargs):
    try:
        check = SmonHttp(kwargs.get('check_id'), kwargs.get('url'), kwargs.get('http_method'), kwargs.get('body'), kwargs.get('name'))
        check.check_http()
        logging.info('HTTP check started')
    except Exception as e:
        logging.error(f'Cannot start HTTP check {e}')


class SmonHttp:
    def __init__(self, check_id: int, url: str, http_method: str, body: str, name: str) -> None:
        self.check_id = check_id
        self.name = name
        self.url = url
        self.http_method = http_method
        self.body = body
        self.result = {}

    def check_http(self):
        self.result['check_type'] = 'http'
        self.result['now_utc'] = get_time()
        self.result['check_id'] = self.check_id
        logging.info(f'url: {self.url}')

        try:
            response = requests.request(self.http_method, f'{self.url}', verify=False)
            response.raise_for_status()
            resp_time = response.elapsed.total_seconds()
            self.result['resp_time'] = resp_time
            self.result['status'] = 1
            self.result['error'] = ''
            logging.info(f'HTTP check result has done in {resp_time} ms')

            try:
                http_method = self.url.split(':')[0]
            except Exception:
                http_method = 'http'

            if http_method == 'https':
                self.check_ssl_expire()

            if self.body:
                body_result = {
                    'check_type': 'body',
                    'check_id': self.check_id,
                    'now_utc': get_time(),
                    'error': '',
                    'status': 1
                }
                try:
                    if self.body not in response.content.decode(encoding='UTF-8'):
                        body_error = f'Body "{self.body}" not found in response content'
                        logging.error(body_error)
                        body_result['status'] = 0
                        body_result['error'] = body_error
                except Exception as e:
                    body_result['error'] = str(e)
                    body_result['status'] = 0
                send_result_to_master(body_result)

        except requests.exceptions.HTTPError as e:
            self.result['resp_time'] = ''
            self.result['status'] = 0
            self.result['error'] = f'Response is: {e.response.status_code} from {self.url}: {e}'
        except requests.exceptions.ConnectTimeout:
            self.result['resp_time'] = ''
            self.result['status'] = 0
            self.result['error'] = f'Connection to {self.url} is timeout'
        except requests.exceptions.ConnectionError:
            self.result['resp_time'] = ''
            self.result['status'] = 0
            self.result['error'] = f'Connection error to {self.url}'
        except Exception as e:
            self.result['resp_time'] = ''
            self.result['status'] = 0
            self.result['error'] = f"error: Unexpected error: {e}"

        send_result_to_master(self.result)

    def check_ssl_expire(self):
        service_ip = self.url.split('/')[2]
        ssl_result = {
            'check_id': self.check_id,
            'check_type': 'ssl',
            'name': self.name,
            'url': self.url
        }

        try:
            service_ip = service_ip.split(':')[0]
        except Exception:
            pass
        try:
            server_port = service_ip.split(':')[1]
        except Exception:
            server_port = 443

        try:
            context = ssl.create_default_context()
            with url_socket.create_connection((service_ip, server_port)) as sock:
                with context.wrap_socket(sock, server_hostname=service_ip) as ssock:
                    data = json.dumps(ssock.getpeercert(), sort_keys=True, indent=4)
            n = json.loads(data)
            ssl_date_exp = datetime.strptime(n['notAfter'], '%b %d %H:%M:%S %Y %Z')
            now_date = datetime.now(timezone('UTC'))
            now_date = now_date.strftime('%b %d %H:%M:%S %Y %Z')
            now_date = datetime.strptime(now_date, '%b %d %H:%M:%S %Y %Z')
            ssl_result['ssl_date_exp'] = str(ssl_date_exp)
            ssl_result['now_date'] = str(now_date)
            ssl_result['error'] = ''
            logging.info(f'SSL check result has done in {self.result}')
        except Exception as error:
            ssl_result['now_date'] = ''
            ssl_result['ssl_date_exp'] = ''
            ssl_result['error'] = str(error)
            logging.error(f'Cannot get SSL information for {self.url}: {error}')

        send_result_to_master(ssl_result)


class SmonDns:
    def __init__(self, check_id: int, resolver: str, record_type: str, domain: str) -> None:
        self.check_id = check_id
        self.resolver = resolver
        self.record_type = record_type
        self.domain = domain
        self.result = {}

    def check_dns(self):
        self.result['check_type'] = 'dns'
        self.result['now_utc'] = get_time()
        self.result['check_id'] = self.check_id

        try:
            my_resolver = dns.resolver.Resolver()
            my_resolver.nameservers = [self.resolver]
            result = my_resolver.query(self.domain, self.record_type)
            resp_time = result.response.time * 1000
            self.result['resp_time'] = resp_time
            self.result['status'] = 1
            self.result['error'] = ''
        except Exception as error:
            self.result['resp_time'] = ''
            self.result['status'] = 0
            self.result['error'] = f'{error}'
            logging.error(f'Cannot DNS check: {error}')
        logging.info(f'DNS check result has done in {self.result}')
        send_result_to_master(self.result)


class SmonPing:
    def __init__(self, check_id: int, server_ip: str, packet_size: int):
        self.check_id = check_id
        self.server_ip = server_ip
        self.packet_size = packet_size
        self.result = {}

    @staticmethod
    def subprocess_execute_with_rc(cmd):
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        stdout, stderr = p.communicate()
        output = stdout.splitlines()
        rc = p.returncode
        return_out = {'output': output, 'error': stderr, 'rc': rc}

        return return_out

    def check_ping(self):
        now_utc = get_time()
        self.result['check_type'] = 'ping'
        self.result['now_utc'] = now_utc
        self.result['check_id'] = self.check_id

        try:
            cmd = f'ping {self.server_ip} -c 1 -q -W 3 -s {self.packet_size}'
            return_out = self.subprocess_execute_with_rc(cmd)

            if not return_out['rc']:
                resp_time = return_out['output'][4].split('/')[5]
                self.result['resp_time'] = resp_time
                self.result['status'] = 1
                self.result['error'] = ''
                logging.info(f'Ping check result has done in {resp_time} ms')
            else:
                self.result['resp_time'] = ''
                self.result['status'] = 0
                self.result['error'] = return_out['error']
                logging.error(f'ping check: {return_out["error"]}')
        except Exception as error:
            self.result['resp_time'] = ''
            self.result['status'] = 0
            self.result['error'] = f'{error}'
            logging.info(f'error: Cannot ping check: {error}')
        logging.info(f'Ping check result has done in {self.result}')
        send_result_to_master(self.result)


class SmonTcp:
    def __init__(self, check_id: int, server_ip: str, port: int):
        self.check_id = check_id
        self.server_ip = server_ip
        self.port = int(port)
        self.result = {}

    def check_tcp(self):
        now_utc = get_time()
        self.result['check_type'] = 'tcp'
        self.result['now_utc'] = now_utc
        self.result['check_id'] = self.check_id
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(5)
            start = time.time()

            try:
                if sock.connect_ex((self.server_ip, self.port)) == 0:
                    end = (time.time()-start)*1000
                    self.result['resp_time'] = end
                    self.result['status'] = 1
                    self.result['error'] = ''
                    logging.info(f'Tcp check result has done in {end} ms')
                else:
                    self.result['resp_time'] = ''
                    self.result['status'] = 0
                    self.result['error'] = 'Port is unreachable'
                    logging.error('Cannot tcp check: Port is unreachable')
            except Exception as e:
                self.result['resp_time'] = ''
                self.result['status'] = 0
                self.result['error'] = f'{e}'
                logging.error(f'Cannot tcp check: {e}')
        logging.info(f'Tcp check result has done in {self.result}')
        send_result_to_master(self.result)


def ask_for_checks():
    agent_uuid = common.get_config_var('agent', 'uuid')
    master = common.get_config_var('master', 'host')
    headers = get_agent_headers()
    try:
        requests.post(f'https://{master}/rmon/agent/hello', headers=headers, json={'uuid': agent_uuid}, verify=False)
    except Exception as e:
        logging.error(f'error: Cannot get checks: {e}')
