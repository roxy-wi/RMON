from flask import render_template, request, jsonify
from flask_jwt_extended import jwt_required

from app.routes.smon import bp
from app.middleware import get_user_params

import app.modules.db.smon as smon_sql
import app.modules.tools.smon as smon_mod
import app.modules.tools.smon_agent as agent_mod
import app.modules.roxywi.common as roxywi_common


@bp.route('/check/<int:multi_check_id>/<int:check_type_id>')
@jwt_required()
@get_user_params()
def get_check(multi_check_id, check_type_id):
    """
    Get the check for the given RMON ID and check type ID.

    Parameters:
    - multi_check_id (int): The ID of the RMON multi check.
    - check_type_id (int): The ID of the check type.

    Returns:
    - flask.Response: The rendered template for the check page.
    """
    smon = smon_sql.select_one_multi_check_join(multi_check_id, check_type_id)
    lang = roxywi_common.get_user_lang_for_flask()
    return render_template('ajax/smon/check.html', smon=smon, lang=lang, check_type_id=check_type_id)


@bp.get('/checks/count')
@jwt_required()
def get_checks_count():
    try:
        smon_mod.check_checks_limit()
    except Exception as e:
        return f'{e}'

    return 'ok'


@bp.post('/checks/move')
@jwt_required()
def move_checks():
    old_agent = int(request.json.get('old_agent'))
    new_agent = int(request.json.get('new_agent'))
    old_agent_ip = smon_sql.get_agent_ip_by_id(old_agent)
    checks = {}

    try:
        for check_type in ('http', 'tcp', 'dns', 'ping', 'smtp', 'rabbitmq'):
            got_checks = smon_sql.select_checks_for_agent(old_agent)
            for c in got_checks:
                checks[c.id] = check_type
                agent_mod.delete_check(old_agent, old_agent_ip, c.id)
                smon_sql.update_check_agent(c.id, new_agent)
    except Exception as e:
        roxywi_common.handle_json_exceptions(e, 'Cannot get checks')

    agent_mod.send_checks(new_agent)

    return jsonify({'checks': str(checks)})
