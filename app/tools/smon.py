import os
import sys
import json
import logging
from datetime import datetime

from flask import Flask, request
from flask_apscheduler import APScheduler

sys.path.append(os.path.join(sys.path[0], '/var/www/smon/'))

import app.modules.db.sql as sql
import app.modules.db.smon as smon_sql
import app.modules.db.history as history_sql
import app.modules.tools.alerting as alerting

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.INFO)


class Config:
    history_range = int(sql.get_setting('keep_history_range'))
    JOBS = [
        {
            "id": "delete_alert_history",
            "func": history_sql.delete_alert_history,
            "args": (history_range, 'RMON'),
            "trigger": "interval",
            "days": 1,
        },
        {
            "id": "delete_smon_history",
            "func": smon_sql.delete_smon_history,
            "trigger": "interval",
            "days": 1,
        }
    ]


app = Flask(__name__)
app.config.from_object(Config())
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()


def send_and_logging(mes, check_name, check_port, tg, slack, pd, user_group, level='warning'):
    if level == 'warning':
        logging.warning(mes)
    elif level == 'critical':
        logging.critical(mes)
    else:
        logging.info(mes)
    mes_for_logs = f'{level}: {mes}'
    mes_for_db = mes
    history_sql.insert_alerts(user_group, level, check_name, check_port, mes_for_db, 'RMON')

    if tg:
        try:
            alerting.telegram_send_mess(mes, level, channel_id=tg)
        except Exception as error:
            logging.error(f'Cannot send a message to Telegram: {error}')

    if slack:
        try:
            alerting.slack_send_mess(mes, level, channel_id=slack)
        except Exception as error:
            logging.error(f'Cannot send a message to Slack: {error}')

    if pd:
        try:
            alerting.pd_send_mess(mes, level, channel_id=pd)
        except Exception as error:
            logging.error(f'Cannot send a message to PagerDuty: {error}')

    try:
        json_for_sending = {"user_group": user_group, "message": mes_for_logs}
        alerting.send_message_to_rabbit(json.dumps(json_for_sending))
        logging.info('Send message to Rabbit')
    except Exception as error:
        logging.error(f'Cannot send a message {error}')


def return_check_params(smon_id: int, check_id: int) -> dict:
    smon = smon_sql.select_one_smon(smon_id, check_id)
    for s in smon:
        params = {
            'check_name': s.smon_id.name,
            'tg': s.smon_id.telegram_channel_id,
            'slack': s.smon_id.slack_channel_id,
            'pd': s.smon_id.pd_channel_id,
            'user_group': s.smon_id.user_group
        }
        if check_id == 1:
            params.setdefault('check_port', s.port)
        else:
            params.setdefault('check_port', '')
        return params


def change_status(smon_id: int, status: int, now_utc: str) -> None:
    logging.info(f'Update status to {status} for {smon_id}')
    now_utc = now_utc.replace('"', '')
    try:
        smon_sql.change_status(status, smon_id)
    except Exception as e:
        logging.error(str(e))
    try:
        smon_sql.add_sec_to_state_time(now_utc, smon_id)
    except Exception as e:
        logging.error(str(e))


def process_agent_check_result(json_object: json) -> None:
    check_types = {
        'tcp': {'id': 1},
        'http': {'id': 2},
        'ping': {'id': 4},
        'dns': {'id': 5}
    }
    smon_id = json_object['check_id']
    now_utc = json_object['now_utc']
    resp_time = json_object['resp_time']
    status = json_object['status']
    error = json_object['error']
    prev_status = smon_sql.select_status(smon_id)
    check_type = check_types[json_object['check_type']]
    check_type_id = check_type['id']
    mes = ''
    level = 'info'
    params = return_check_params(smon_id, check_type_id)
    logging.info(f'Processing agent check result. Check type: {json_object["check_type"]}, check id: {smon_id}')

    smon_sql.response_time(resp_time, smon_id)
    smon_sql.insert_smon_history(smon_id, resp_time, status, check_type_id, error)

    if status == 1:
        if prev_status == 0 or prev_status == 3:
            change_status(smon_id, status, now_utc)
            mes = f'Check {params["check_name"]} is available'
    else:
        if prev_status == 1 or prev_status == 3:
            change_status(smon_id, status, now_utc)
            mes = f'Check {params["check_name"]} is not available: {error}'
            level = 'warning'

    if mes:
        send_and_logging(mes, params['check_name'], params['check_port'], params['tg'], params['slack'], params['pd'],
                         params['user_group'], level)


def process_agent_check_result_ssl(json_object: json) -> None:
    warning_days = sql.get_setting('ssl_expire_warning_alert')
    critical_days = sql.get_setting('ssl_expire_critical_alert')
    name = json_object['name']
    check_id = json_object['check_id']
    ssl_date_exp = datetime.strptime(json_object['ssl_date_exp'], '%Y-%m-%d %H:%M:%S')
    now_date = datetime.strptime(json_object['now_date'], '%Y-%m-%d %H:%M:%S')
    url = json_object['url']
    params = return_check_params(check_id, 2)
    mes = ''
    level = 'info'
    logging.info(f'Processing agent check SSL result. Check type: {json_object["check_type"]}, check id: {check_id}')

    if (ssl_date_exp - now_date).days < warning_days:
        alert = 'ssl_expire_warning_alert'
        need_alert = smon_sql.get_smon_alert_status(check_id, alert)
        if need_alert == 0:
            smon_sql.update_smon_alert_status(check_id, 1, alert)
            mes = f'A SSL certificate on {name} {url} will expire in less than {warning_days} days'
            level = 'warning'
    else:
        smon_sql.update_smon_alert_status(check_id, 0, 'ssl_expire_warning_alert')

    if (ssl_date_exp - now_date).days < critical_days:
        alert = 'ssl_expire_critical_alert'
        need_alert = smon_sql.get_smon_alert_status(check_id, alert)
        if need_alert == 0:
            mes = f'A SSL certificate on {name} {url} will expire in less than {critical_days} days'
            level = 'critical'
            smon_sql.update_smon_alert_status(check_id, 1, alert)
    else:
        smon_sql.update_smon_alert_status(check_id, 0, 'ssl_expire_critical_alert')

    if mes:
        send_and_logging(mes, params['check_name'], url, params['tg'], params['slack'], params['pd'],
                         params['user_group'], level)

    try:
        smon_sql.update_smon_ssl_expire_date(check_id, str(ssl_date_exp))
    except Exception as error:
        logging.error(f'error: Cannot update SSL expire date for {name} {url}: {error}')


def process_agent_check_result_body(json_object: json) -> None:
    smon_id = json_object['check_id']
    status = json_object['status']
    now_utc = json_object['now_utc']
    error = json_object['error']
    prev_status = smon_sql.select_body_status(smon_id)
    params = return_check_params(smon_id, 2)
    level = 'info'
    mes = ''
    logging.info(f'Processing agent check BODY result. Check type: {json_object["check_type"]}, check id: {smon_id}')

    smon_sql.insert_smon_history(smon_id, '', status, 2, error)

    if status == 1:
        if prev_status == 0 or prev_status == 3:
            smon_sql.change_body_status(status, smon_id)
            smon_sql.add_sec_to_state_time(now_utc, smon_id)
            mes = f'The body is ok now on {params["check_name"]}'
    else:
        if prev_status == 1 or prev_status == 3:
            smon_sql.change_body_status(status, smon_id)
            smon_sql.add_sec_to_state_time(now_utc, smon_id)
            mes = f'Check {params["check_name"]} is not available: {error}'
            level = 'warning'

    if mes:
        send_and_logging(mes, params['check_name'], params['check_port'], params['tg'], params['slack'], params['pd'],
                         params['user_group'], level)


@app.post('/agent/check/result')
def agent_check_result():
    data = request.get_json()
    check_result_function = {
        'tcp': process_agent_check_result,
        'ping': process_agent_check_result,
        'dns': process_agent_check_result,
        'http': process_agent_check_result,
        'ssl': process_agent_check_result_ssl,
        'body': process_agent_check_result_body,
    }
    check_result_function[data['check_type']](data)
    return 'ok'


if __name__ == '__main__':
    app.run(host="0.0.0.0")
