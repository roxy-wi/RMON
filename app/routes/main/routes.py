import sys
import pytz

from flask import render_template, request, session, g, abort
from flask_login import login_required

sys.path.insert(0,"/var/www/rmon/app")

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


@app.errorhandler(403)
@get_user_params()
def page_is_forbidden(e):
    kwargs = {
        'user_params': g.user_params,
        'title': e,
        'e': e
    }
    return render_template('error.html', **kwargs), 403


@app.errorhandler(404)
@get_user_params()
def page_not_found(e):
    kwargs = {
        'user_params': g.user_params,
        'title': e,
        'e': e
    }
    return render_template('error.html', **kwargs), 404


@app.errorhandler(405)
@get_user_params()
def method_not_allowed(e):
    kwargs = {
        'user_params': g.user_params,
        'title': e,
        'e': e
    }
    return render_template('error.html', **kwargs), 405


@app.errorhandler(500)
@get_user_params()
def internal_error(e):
    kwargs = {
        'user_params': g.user_params,
        'title': e,
        'e': e
    }
    return render_template('error.html', **kwargs), 500


@app.before_request
def make_session_permanent():
    session.permanent = True


@bp.route('/nettools')
@login_required
@get_user_params(1)
def nettools():
    return render_template('nettools.html', lang=g.user_params['lang'])


@bp.post('/nettools/<check>')
@login_required
def nettols_check(check):
    server_from = common.checkAjaxInput(request.form.get('server_from'))
    server_to = common.is_ip_or_dns(request.form.get('server_to'))
    action = common.checkAjaxInput(request.form.get('nettools_action'))
    port_to = common.checkAjaxInput(request.form.get('nettools_telnet_port_to'))
    dns_name = common.checkAjaxInput(request.form.get('nettools_nslookup_name'))
    dns_name = common.is_ip_or_dns(dns_name)
    record_type = common.checkAjaxInput(request.form.get('nettools_nslookup_record_type'))

    if check == 'icmp':
        return nettools_mod.ping_from_server(server_from, server_to, action)
    elif check == 'tcp':
        return nettools_mod.telnet_from_server(server_from, server_to, port_to)
    elif check == 'dns':
        return nettools_mod.nslookup_from_server(server_from, dns_name, record_type)
    else:
        return 'error: Wrong check'


@bp.route('/history/<service>/<server_ip>')
@login_required
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
        abort(404, f'History not found')

    kwargs = {
        'user_subscription': roxywi_common.return_user_subscription(),
        'users': user_sql.select_users(),
        'serv': server_ip,
        'service': service,
        'history': history
    }

    return render_template('history.html', **kwargs)


@bp.route('/servers')
@login_required
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
