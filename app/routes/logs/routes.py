from flask import render_template, request, g
from flask_jwt_extended import jwt_required

from app.routes.logs import bp
from app.middleware import get_user_params
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
import app.modules.roxy_wi_tools as roxy_wi_tools

get_config = roxy_wi_tools.GetConfigVar()


@bp.before_request
@jwt_required()
def before_request():
    """ Protect all the admin endpoints. """
    pass


@bp.route('/internal')
@get_user_params()
def logs_internal():
    log_type = request.args.get('type')
    log_file = request.args.get('log_file')
    log_path = get_config.get_config_var('main', 'log_path')
    selects = roxywi_common.get_files(log_path, file_format="log")

    if log_type == '2':
        roxywi_auth.page_for_admin(level=2)
    else:
        roxywi_auth.page_for_admin()

    if log_type is None:
        selects.append(['fail2ban.log', 'fail2ban.log'])
        selects.append(['rmon.error.log', 'error.log'])
        selects.append(['rmon.access.log', 'access.log'])

    kwargs = {
        'selects': selects,
        'serv': log_file,
        'lang': g.user_params['lang']
    }
    return render_template('logs_internal.html', **kwargs)
