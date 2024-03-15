import os
import time
from datetime import datetime
import logging

import psutil
from flask import Flask, request
from flask_apscheduler import APScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

import smon_checks
import smon_agent_common as common

logging.basicConfig(filename='/var/log/roxy-wi/smon-agent.log', format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)

app = Flask(__name__)
scheduler = APScheduler()
scheduler.api_enabled = True
scheduler.init_app(app)
scheduler.start()

VERSION = '0.1'
AGENT_UUID = common.get_config_var('agent', 'uuid')


def my_listener(event):
    if event.exception:
        logging.error(f'The job crashed {event.exception}')


scheduler.add_listener(my_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)


def add_tcp_to_scheduler(json_data):
    job_name = f"{json_data['check_type']}_{json_data['check_id']}"
    interval = int(json_data['interval'])
    scheduler.add_job(func=smon_checks.check_tcp, trigger='interval', id=str(json_data['check_id']), name=job_name, seconds=interval, kwargs=json_data, replace_existing=True)

    return 'ok'


def add_ping_to_scheduler(json_data):
    job_name = f"{json_data['check_type']}_{json_data['check_id']}"
    interval = int(json_data['interval'])
    scheduler.add_job(func=smon_checks.check_ping, trigger='interval', id=str(json_data['check_id']), name=job_name, seconds=interval, kwargs=json_data, replace_existing=True)

    return 'ok'


def add_http_to_scheduler(json_data):
    job_name = f"{json_data['check_type']}_{json_data['check_id']}"
    interval = int(json_data['interval'])
    scheduler.add_job(func=smon_checks.check_http, trigger='interval', id=str(json_data['check_id']), name=job_name, seconds=interval, kwargs=json_data, replace_existing=True)

    return 'ok'


def add_dns_to_scheduler(json_data):
    job_name = f"{json_data['check_type']}_{json_data['check_id']}"
    interval = int(json_data['interval'])
    scheduler.add_job(func=smon_checks.check_dns, trigger='interval', id=str(json_data['check_id']), name=job_name, seconds=interval, kwargs=json_data, replace_existing=True)

    return 'ok'


@app.before_request
def check_agent_uuid():
    """
    Check Agent UUID

    This method is a decorator for the Flask `before_request` hook that is used to check if the Agent UUID in the request headers matches the expected UUID.

    Returns:
        dict: If the Agent UUID is invalid, a dictionary with an 'error' key and corresponding error message value is returned. Otherwise, None is returned.
    """
    if request.endpoint != 'root' and request.endpoint != 'ret_version':
        if request.headers.get('Agent-UUID') != AGENT_UUID:
            return {'error': 'Invalid Agent UUID'}, 401


@app.route('/')
def root():
    return 'Welcome to the RMON Agent!'


@app.route('/version')
def ret_version():
    return {'version': VERSION}


@app.route('/uptime')
def get_uptime():
    p = psutil.Process(os.getpid())
    uptime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.create_time()))
    return {'uptime': uptime}


@app.route('/checks', methods=['GET'])
def return_checks():
    checks = {}
    for c in scheduler.get_jobs():
        print(c)
        checks.setdefault(c.kwargs.get('check_id'), c.kwargs)
        checks[c.kwargs.get('check_id')].setdefault('next_run_time', c.next_run_time)
    return checks


@app.route('/check/<int:check_id>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def check_status(check_id):
    checks = {
        'tcp': add_tcp_to_scheduler,
        'http': add_http_to_scheduler,
        'ping': add_ping_to_scheduler,
        'dns': add_dns_to_scheduler,
    }

    if request.method == 'GET':
        try:
            r_job = scheduler.get_job(str(check_id))
            if r_job:
                return {
                    'name': r_job.name,
                    'kwargs': r_job.kwargs,
                    'interval': r_job.kwargs.get('interval'),
                    'next_run_time': r_job.next_run_time
                }
            else:
                return {'warning': 'Check not found'}, 404
        except Exception as e:
            mess = {'error': f"Cannot get check: {e}"}
            logging.error(mess)
            return mess, 500
    elif request.method == 'POST':
        data = request.get_json()
        data['check_id'] = check_id
        job = scheduler.get_job(str(check_id))
        if job:
            mess = {'warning': f"Conflict job already exists"}
            logging.error(mess)
            return mess, 409
        try:
            resp = checks[data['check_type']](data)
        except Exception as e:
            mess = {'error': f"Cannot add check {check_id}: {e}"}
            logging.error(mess)
            return mess, 500
        return {'message': resp}, 201
    elif request.method == 'PUT':
        data = request.get_json()
        data['check_id'] = check_id
        try:
            resp = checks[data['check_type']](data)
        except Exception as e:
            mess = {'error': f"Cannot modify check {check_id}: {e}"}
            logging.error(mess)
            return mess, 500
        return {'message': f'Check update successful: {resp}'}
    elif request.method == 'DELETE':
        try:
            scheduler.remove_job(str(check_id))
        except Exception as e:
            mess = {'error': f"Cannot delete check {check_id}: {e}"}
            return mess, 500
        return {'message': f'Check {check_id}: delete successful'}


@app.route('/check/<int:check_id>/<action>')
def run_check(check_id, action):
    try:
        job = scheduler.get_job(str(check_id))
        if not job:
            return {'warning': f'Check not found'}, 404
    except Exception as e:
        mess = {'error': f"Cannot get check: {e}"}
        logging.error(mess)
        return mess, 500
    if action == 'run':
        try:
            resp = scheduler.add_job(func=job.func, trigger='date', id=str(check_id), name=job.name, run_date=datetime.now(), kwargs=job.kwargs)
            return {'message': f'Check run initiated: {resp}'}, 201
        except Exception as e:
            mess = {'error': f"Cannot run check: {e}"}
            logging.error(mess)
            return mess, 500
    elif action == 'resume':
        try:
            scheduler.resume_job(str(check_id))
            return {'message': f'Check resume initiated'}, 201
        except Exception as e:
            mess = {'error': f"Cannot resume check: {e}"}
            logging.error(mess)
            return mess, 500
    elif action == 'pause':
        try:
            scheduler.pause_job(str(check_id))
            return {'message': f'Check pause initiated'}, 201
        except Exception as e:
            mess = {'error': f"Cannot pause check: {e}"}
            logging.error(mess)
            return mess, 500


@app.route('/agent/<action>')
def agent_action(action):
    try:
        if action == 'start':
            scheduler.start()
        elif action == 'pause':
            scheduler.pause()
        elif action == 'stop':
            scheduler.shutdown(wait=False)
        elif action == 'resume':
            scheduler.resume()
    except Exception as e:
        mess = {'error': f"Cannot {action} agent: {e}"}
        logging.error(mess)
        return mess, 500
    return {'message': f'Agent {action}ed'}


if __name__ == '__main__':
    app.run(host="0.0.0.0")
