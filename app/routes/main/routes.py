import os
from typing import Union, Literal

from flask import render_template, g, send_from_directory, jsonify
from flask_jwt_extended import jwt_required
from flask_pydantic import validate
from pydantic import IPvAnyAddress

from app import app, cache
from app.routes.main import bp
import app.modules.db.user as user_sql
import app.modules.db.server as server_sql
import app.modules.db.history as history_sql
from app.middleware import get_user_params
import app.modules.common.common as common
import app.modules.roxywi.roxy as roxy
import app.modules.roxywi.nettools as nettools_mod
import app.modules.roxywi.common as roxywi_common
import app.modules.server.server as server_mod
from app.modules.roxywi.class_models import ErrorResponse, NettoolsRequest, DomainName, EscapedString
from app.modules.db.db_model import conn


@app.before_request
def db_connect():
    if conn.is_closed():
        conn.connect(reuse_if_open=True)


@app.teardown_request
def db_close(exc):
    if not conn.is_closed():
        conn.close()


@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    return common.get_time_zoned_date(date, fmt)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'images/favicon/favicon.ico', mimetype='image/vnd.microsoft.icon')


@bp.route('/nettools')
@jwt_required()
@get_user_params(1)
def nettools():
    return render_template('nettools.html', lang=g.user_params['lang'])


@bp.post('/nettools/<check>')
@validate(body=NettoolsRequest)
@jwt_required()
def nettools_check(check, body: NettoolsRequest):
    if check == 'icmp':
        try:
            return nettools_mod.ping_from_server(body.server_from, str(body.server_to), body.action)
        except Exception as e:
            return ErrorResponse(error=f'Cannot ping: {e}').model_dump(mode='json'), 500
    elif check == 'tcp':
        try:
            return nettools_mod.telnet_from_server(body.server_from, str(body.server_to), body.port)
        except Exception as e:
            return ErrorResponse(error=f'Cannot check port: {e}').model_dump(mode='json'), 500
    elif check == 'dns':
        try:
            return nettools_mod.nslookup_from_server(body.server_from, body.dns_name, body.record_type)
        except Exception as e:
            return ErrorResponse(error=f'Cannot lookup: {e}').model_dump(mode='json'), 500
    elif check == 'whois':
        try:
            return jsonify(nettools_mod.whois_check(body.dns_name))
        except Exception as e:
            return ErrorResponse(error=f'Cannot make whois: {e}').model_dump(mode='json'), 500
    elif check == 'ipcalc':
        try:
            ip_add = str(body.ip)
            netmask = int(body.netmask)
        except Exception as e:
            return ErrorResponse(error=f'Cannot calc: {e}').model_dump(mode='json'), 500

        try:
            return jsonify(nettools_mod.ip_calc(ip_add, netmask))
        except Exception as e:
            return ErrorResponse(error=f'Cannot calc: {e}').model_dump(mode='json'), 500
    else:
        return 'error: Wrong check'


@bp.route('/history/<service>/<server_ip>')
@jwt_required()
@get_user_params()
@validate()
def service_history(service: Literal['server', 'user'], server_ip: Union[IPvAnyAddress, DomainName, EscapedString]):
    history = ''

    if service == 'server':
        if roxywi_common.check_is_server_in_group(server_ip):
            server_id = server_sql.select_server_id_by_ip(server_ip)
            history = history_sql.select_action_history_by_server_id(server_id)
    elif service == 'user':
        history = history_sql.select_action_history_by_user_id(server_ip)

    kwargs = {
        'user_subscription': roxywi_common.return_user_subscription(),
        'users': user_sql.select_users(),
        'serv': server_ip,
        'service': service,
        'history': history
    }

    return render_template('history.html', **kwargs)


@bp.route('/internal/show_version')
@cache.cached()
def show_roxywi_version():
    return jsonify(roxy.versions())


@bp.route('/portscanner/scan/<int:server_id>', defaults={'server_ip': None})
@bp.route('/portscanner/scan/<server_ip>', defaults={'server_id': None})
def scan_port(server_id, server_ip):
    if server_ip:
        ip = server_ip
    else:
        server = server_sql.select_servers(id=server_id)
        ip = ''

        for s in server:
            ip = s[2]

    cmd = f"sudo nmap -sS {ip} |grep -E '^[[:digit:]]'|sed 's/  */ /g'"
    cmd1 = f"sudo nmap -sS {ip} |head -5|tail -2"

    stdout, stderr = server_mod.subprocess_execute(cmd)
    stdout1, stderr1 = server_mod.subprocess_execute(cmd1)

    if stderr != '':
        return f'error: {stderr}'
    else:
        lang = roxywi_common.get_user_lang_for_flask()
        return render_template('ajax/scan_ports.html', ports=stdout, info=stdout1, lang=lang)
