import pytz
from flask import render_template, request, g
from flask_jwt_extended import jwt_required

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
import app.modules.tools.smon as smon_mod
import app.modules.tools.common as tools_common


@bp.before_request
@jwt_required()
def before_request():
    """ Protect all the admin endpoints. """
    pass


@bp.route('')
@get_user_params()
def admin():
    """
    Renders the admin page with appropriate data.

    :return: The rendered template for the admin page.
    """
    roxywi_auth.page_for_admin(level=2)
    user_group = roxywi_common.get_user_group(id=1)
    if g.user_params['role'] == 1:
        users = user_sql.select_users()
        servers = server_sql.select_servers(full=1)
        sshs = cred_sql.select_ssh()
    else:
        users = user_sql.select_users(group=user_group)
        servers = roxywi_common.get_dick_permit(virt=1, disable=0, only_group=1)
        sshs = cred_sql.select_ssh(group=user_group)

    kwargs = {
        'lang': g.user_params['lang'],
        'users': users,
        'group_id': group_sql.select_groups(),
        'group': roxywi_common.get_user_group(id=1),
        'sshs': sshs,
        'servers': servers,
        'roles': sql.select_roles(),
        'timezones': pytz.all_timezones,
        'settings': sql.get_setting('', all=1),
        'ldap_enable': sql.get_setting('ldap_enable'),
        'guide_me': 1,
        'user_subscription': roxywi_common.return_user_subscription(),
        'users_roles': user_sql.select_users_roles(),
        'user_roles': user_sql.select_user_roles_by_group(user_group),
    }

    return render_template('admin.html', **kwargs)


@bp.route('/tools')
def show_tools():
    """
    Request handler for /tools route.

    This method is responsible for rendering the tools page for superAdmin users.
    It retrieves the user's preferred language and gets the status of services
    from the tools_common module. The services status is then rendered using
    the 'ajax/load_services.html' template.

    Returns:
        str: The rendered template.

    Raises:
        Exception: If an error occurs while retrieving the services status.
    """
    roxywi_auth.page_for_admin()
    lang = roxywi_common.get_user_lang_for_flask()
    try:
        services = tools_common.get_services_status(update_cur_ver=1)
    except Exception as e:
        return str(e)

    return render_template('ajax/load_services.html', services=services, lang=lang)


@bp.route('/tools/update/<service>')
def update_tools(service):
    """
    Updates the tools for the specified service.

    Parameters:
    - service: A string representing the service for which the tools need to be updated.

    Returns:
    - If the update is successful, the method returns the result of the update.
    - If an error occurs during the update, the method returns an error message.
    """
    roxywi_auth.page_for_admin()

    try:
        return tools_common.update_roxy_wi(service)
    except Exception as e:
        return f'{e}'


@bp.route('/tools/action/<service>/<action>')
def action_tools(service, action):
    """
    Perform an action on a service.

    Parameters:
    - service (str): The name of the service to perform the action on.
    - action (str): The action to be performed on the service. It must be one of 'start', 'stop', or 'restart'.

    Returns:
    - The result of the action performed on the service.
    Note:
    - The 'roxywi_auth.page_for_admin()' function is called before performing the action to ensure that only superAdmin can access this endpoint.
    - If the provided action is not one of 'start', 'stop', or 'restart', an error message will be returned.
    """
    roxywi_auth.page_for_admin()
    if action not in ('start', 'stop', 'restart'):
        return 'error: wrong action'

    return roxy.action_service(action, service)


@bp.route('/update')
def update_roxywi():
    """
    This method is used to update the RMON platform. It retrieves the list of versions available for update, the status
    of services running, and the user's preferred language for the Flask framework. It then renders the 'ajax/load_updateroxywi.html' template with the retrieved data.

    Returns:
        The rendered template with the services, versions, and language information.
    """
    roxywi_auth.page_for_admin()
    versions = roxy.versions()
    services = tools_common.get_services_status()
    lang = roxywi_common.get_user_lang_for_flask()

    return render_template(
        'ajax/load_updateroxywi.html', services=services, versions=versions, lang=lang
    )


@bp.route('/update/check')
def check_update():
    """
    This method is responsible for checking the update of the system.
    It performs the following steps:

    1. Authenticates the user as an supeAadmin using the roxywi_auth.page_for_admin() method.
    2. Runs the "check_new_version" job using the scheduler.run_job() method.
    3. Returns the string 'ok' to indicate successful completion.

    Returns:
        str: A string 'ok' indicating successful completion.
    """
    roxywi_auth.page_for_admin()
    scheduler.run_job('check_new_version')
    return 'ok'


@bp.post('/setting/<param>')
def update_settings(param):
    """
    Updates the specified setting with the given parameter value.

    Parameters:
    - param (str): The name of the setting to be updated.

    Returns:
    - str: A string indicating the success of the update.
    """
    roxywi_auth.page_for_admin(level=2)
    val = request.form.get('val').replace('92', '/')
    user_group = roxywi_common.get_user_group(id=1)
    if sql.update_setting(param, val, user_group):
        roxywi_common.logging('RMON server', f'The {param} setting has been changed to: {val}', roxywi=1, login=1)

        if param == 'master_port':
            try:
                smon_mod.change_smon_port(val)
            except Exception as e:
                return f'{e}'

        return 'Ok'
