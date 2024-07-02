import os
import pytz

from flask import render_template, request, g, abort, send_from_directory, jsonify, redirect, url_for
from flask_jwt_extended import jwt_required
from flask_pydantic.exceptions import ValidationError

from app import app, cache
from app.routes.main import bp
import app.modules.db.sql as sql
import app.modules.db.cred as cred_sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
import app.modules.db.history as history_sql
from app.middleware import get_user_params
import app.modules.common.common as common
import app.modules.roxywi.roxy as roxy
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.nettools as nettools_mod
import app.modules.roxywi.common as roxywi_common
import app.modules.server.server as server_mod
from app.views.server.views import ServerGroupView
from app.modules.roxywi.exception import RoxywiValidationError
from app.modules.roxywi.class_models import ErrorResponse

bp.add_url_rule('/group', view_func=ServerGroupView.as_view('group'))


@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    return common.get_time_zoned_date(date, fmt)


@app.errorhandler(RoxywiValidationError)
def handle_pydantic_validation_errors(e):
    return ErrorResponse(error=str(e)), 400


@app.errorhandler(ValidationError)
def handle_pydantic_validation_errors1(e):
    errors = []
    if e.body_params:
        req_type = e.body_params
    elif e.form_params:
        req_type = e.form_params
    elif e.path_params:
        req_type = e.path_params
    else:
        req_type = e.query_params
    for er in req_type:
        if len(er["loc"]) > 0:
            errors.append(f'{er["loc"][0]}: {er["msg"]}')
        else:
            errors.append(er["msg"])
    return ErrorResponse(error=errors).model_dump(mode='json'), 400


@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': str(e)}), 400


@app.errorhandler(401)
def no_auth(e):
    if 'api' in request.url:
        return jsonify({'error': str(e)}), 401
    return redirect(url_for('login_page'))


@app.errorhandler(403)
@get_user_params()
def page_is_forbidden(e):
    if 'api' in request.url:
        return jsonify({'error': str(e)}), 403
    kwargs = {
        'user_params': g.user_params,
        'title': e,
        'e': e
    }
    return render_template('error.html', **kwargs), 403


@app.errorhandler(404)
@get_user_params()
def page_not_found(e):
    if 'api' in request.url:
        return jsonify({'error': str(e)}), 404
    kwargs = {
        'user_params': g.user_params,
        'title': e,
        'e': e
    }
    return render_template('error.html', **kwargs), 404


@app.errorhandler(405)
@get_user_params()
def method_not_allowed(e):
    if 'api' in request.url:
        return jsonify({'error': str(e)}), 405
    kwargs = {
        'user_params': g.user_params,
        'title': e,
        'e': e
    }
    return render_template('error.html', **kwargs), 405


@app.errorhandler(409)
@get_user_params()
def conflict(e):
    return jsonify({'error': str(e)}), 409


@app.errorhandler(415)
@get_user_params()
def unsupported_media_type(e):
    return jsonify({'error': str(e)}), 415


@app.errorhandler(500)
@get_user_params()
def internal_error(e):
    if 'api' in request.url:
        return jsonify({'error': str(e)}), 500
    kwargs = {
        'user_params': g.user_params,
        'title': e,
        'e': e
    }
    return render_template('error.html', **kwargs), 500


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
@jwt_required()
def nettools_check(check):
    server_from = common.checkAjaxInput(request.form.get('server_from'))
    server_to = common.is_ip_or_dns(request.form.get('server_to'))
    action = common.checkAjaxInput(request.form.get('nettools_action'))
    port_to = common.checkAjaxInput(request.form.get('nettools_telnet_port_to'))
    dns_name = common.checkAjaxInput(request.form.get('nettools_nslookup_name'))
    dns_name = common.is_ip_or_dns(dns_name)
    record_type = common.checkAjaxInput(request.form.get('nettools_nslookup_record_type'))
    domain_name = common.is_ip_or_dns(request.form.get('nettools_whois_name'))

    if check == 'icmp':
        try:
            return nettools_mod.ping_from_server(server_from, server_to, action)
        except Exception as e:
            return str(e)
    elif check == 'tcp':
        try:
            return nettools_mod.telnet_from_server(server_from, server_to, port_to)
        except Exception as e:
            return str(e)
    elif check == 'dns':
        try:
            return nettools_mod.nslookup_from_server(server_from, dns_name, record_type)
        except Exception as e:
            return str(e)
    elif check == 'whois':
        try:
            return jsonify(nettools_mod.whois_check(domain_name))
        except Exception as e:
            return str(e)
    else:
        return 'error: Wrong check'


@bp.route('/history/<service>/<server_ip>')
@jwt_required()
@get_user_params()
def service_history(service, server_ip):
    history = ''
    server_ip = common.checkAjaxInput(server_ip)

    if service == 'server':
        if roxywi_common.check_is_server_in_group(server_ip):
            server_id = server_sql.select_server_id_by_ip(server_ip)
            history = history_sql.select_action_history_by_server_id(server_id)
    elif service == 'user':
        history = history_sql.select_action_history_by_user_id(server_ip)
    else:
        abort(404, 'History not found')

    kwargs = {
        'user_subscription': roxywi_common.return_user_subscription(),
        'users': user_sql.select_users(),
        'serv': server_ip,
        'service': service,
        'history': history
    }

    return render_template('history.html', **kwargs)


@bp.route('/servers')
@jwt_required()
@get_user_params()
def servers():
    roxywi_auth.page_for_admin(level=2)

    user_group = roxywi_common.get_user_group(id=1)
    kwargs = {
        'h2': 1,
        'users': user_sql.select_users(group=user_group),
        'groups': group_sql.select_groups(),
        'servers': roxywi_common.get_dick_permit(disable=0, only_group=1),
        'roles': sql.select_roles(),
        'sshs': cred_sql.select_ssh(group=user_group),
        'group': roxywi_common.get_user_group(id=1),
        'timezones': pytz.all_timezones,
        'settings': sql.get_setting('', all=1),
        'page': 'servers.py',
        'ldap_enable': sql.get_setting('ldap_enable'),
        'user_roles': user_sql.select_user_roles_by_group(user_group),
        'lang': g.user_params['lang']
    }

    return render_template('servers.html', **kwargs)


@bp.route('/internal/show_version')
@cache.cached()
def show_roxywi_version():
    return render_template('ajax/check_version.html', versions=roxy.versions())


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


@bp.route('/cpu-ram-metrics/<server_id>')
@jwt_required()
@get_user_params()
def cpu_ram_metrics(server_id):
    kwargs = {
        'id': server_id,
        'lang': g.user_params['lang']
    }

    return render_template('ajax/overviewServers.html', **kwargs)
