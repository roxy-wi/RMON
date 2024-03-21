import pytz
from flask import render_template, request, g
from flask_login import login_required

from app import scheduler
from app.routes.admin import bp
import app.modules.db.sql as sql
import app.modules.db.cred as cred_sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
from app.middleware import get_user_params
import app.modules.roxywi.roxy as roxy
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.common as tools_common


@bp.before_request
@login_required
def before_request():
    """ Protect all the admin endpoints. """
    pass


@bp.route('')
@get_user_params()
def admin():
    roxywi_auth.page_for_admin()

    kwargs = {
        'lang': g.user_params['lang'],
        'users': user_sql.select_users(),
        'groups': group_sql.select_groups(),
        'sshs': cred_sql.select_ssh(),
        'servers': server_sql.select_servers(full=1),
        'roles': sql.select_roles(),
        'timezones': pytz.all_timezones,
        'settings': sql.get_setting('', all=1),
        'ldap_enable': sql.get_setting('ldap_enable'),
        'masters': server_sql.select_servers(get_master_servers=1),
        'user_subscription': roxywi_common.return_user_subscription()
    }

    return render_template('admin.html', **kwargs)


@bp.route('/tools')
def show_tools():
    roxywi_auth.page_for_admin()
    lang = roxywi_common.get_user_lang_for_flask()
    try:
        services = tools_common.get_services_status(update_cur_ver=1)
    except Exception as e:
        return str(e)

    return render_template('ajax/load_services.html', services=services, lang=lang)


@bp.route('/tools/update/<service>')
def update_tools(service):
    roxywi_auth.page_for_admin()

    try:
        return tools_common.update_roxy_wi(service)
    except Exception as e:
        return f'error: {e}'


@bp.route('/tools/action/<service>/<action>')
def action_tools(service, action):
    roxywi_auth.page_for_admin()
    if action not in ('start', 'stop', 'restart'):
        return 'error: wrong action'

    return roxy.action_service(action, service)


@bp.route('/update')
def update_roxywi():
    roxywi_auth.page_for_admin()
    versions = roxy.versions()
    services = tools_common.get_services_status()
    lang = roxywi_common.get_user_lang_for_flask()

    return render_template(
        'ajax/load_updateroxywi.html', services=services, versions=versions, lang=lang
    )


@bp.route('/update/check')
def check_update():
    roxywi_auth.page_for_admin()
    scheduler.run_job('check_new_version')
    return 'ok'


@bp.post('/setting/<param>')
def update_settings(param):
    roxywi_auth.page_for_admin(level=2)
    val = request.form.get('val').replace('92', '/')
    user_group = roxywi_common.get_user_group(id=1)
    if sql.update_setting(param, val, user_group):
        roxywi_common.logging('Roxy-WI server', f'The {param} setting has been changed to: {val}', roxywi=1, login=1)

        return 'Ok'
