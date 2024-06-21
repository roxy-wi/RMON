import json

from flask import render_template, request, jsonify, g
from flask_login import login_required

from app.routes.smon import bp
from app.middleware import get_user_params

import app.modules.db.smon as smon_sql
import app.modules.tools.smon as smon_mod
import app.modules.tools.smon_agent as agent_mod
import app.modules.roxywi.common as roxywi_common


@bp.route('/check', methods=['POST', 'PUT', 'DELETE'])
@login_required
def smon_add():
    json_data = request.get_json()
    user_group = roxywi_common.get_user_group(id=1)
    if request.method == "POST":
        try:
            smon_mod.check_checks_limit()
        except Exception as e:
            return f'{e}'
        try:
            last_id = smon_mod.create_smon(json_data, user_group)
        except Exception as e:
            return str(e), 200
        return str(last_id)
    elif request.method == "PUT":
        check_id = json_data['check_id']

        if roxywi_common.check_user_group_for_flask():
            try:
                status = smon_mod.update_smon(check_id, json_data, user_group)
            except Exception as e:
                return f'{e}', 200
            else:
                return status, 201
    elif request.method == "DELETE":
        check_id = json_data['check_id']

        if roxywi_common.check_user_group_for_flask():
            try:
                status = smon_mod.delete_smon(check_id, user_group)
            except Exception as e:
                return f'{e}', 200
            else:
                return status


@bp.route('/check/settings/<int:smon_id>/<int:check_type_id>')
@login_required
@get_user_params()
def check(smon_id, check_type_id):
    smon = smon_sql.select_one_smon(smon_id, check_type_id)
    settings = {}
    for s in smon:
        try:
            group_name = smon_sql.get_smon_group_name_by_id(s.smon_id.group_id)
        except Exception:
            group_name = ''
        settings = {
            'id': s.smon_id.id,
            'name': s.smon_id.name,
            'interval': str(s.interval),
            'agent_id': str(s.agent_id),
            'enabled': s.smon_id.en,
            'status': s.smon_id.status,
            'http': s.smon_id.http,
            'desc': s.smon_id.desc,
            'tg': s.smon_id.telegram_channel_id,
            'slack': s.smon_id.slack_channel_id,
            'pd': s.smon_id.pd_channel_id,
            'mm': s.smon_id.mm_channel_id,
            'check_type': s.smon_id.check_type,
            'timeout': s.smon_id.check_timeout,
            'group': group_name,
        }
        if check_type_id in (1, 5):
            settings.setdefault('port', s.port)

        if check_type_id != 2:
            settings.setdefault('server_ip', str(s.ip))
        if check_type_id == 2:
            settings.setdefault('url', s.url)
            settings.setdefault('method', s.method)
            settings.setdefault('body', s.body)
            settings.setdefault('status_code', s.accepted_status_codes)
            if s.body_req:
                settings.setdefault('body_req', json.loads(s.body_req))
            else:
                settings.setdefault('body_req', '')
            if s.headers:
                settings.setdefault('header_req', str(s.headers))
            else:
                settings.setdefault('header_req', '')
        elif check_type_id == 4:
            settings.setdefault('packet_size', s.packet_size)
        elif check_type_id == 5:
            settings.setdefault('resolver', s.resolver)
            settings.setdefault('record_type', s.record_type)

    return jsonify(settings)


@bp.route('/check/<int:smon_id>/<int:check_type_id>')
@login_required
@get_user_params()
def get_check(smon_id, check_type_id):
    """
    Get the check for the given RMON ID and check type ID.

    Parameters:
    - smon_id (int): The ID of the RMON.
    - check_type_id (int): The ID of the check type.

    Returns:
    - flask.Response: The rendered template for the check page.
    """
    smon = smon_sql.select_one_smon(smon_id, check_type_id)
    lang = roxywi_common.get_user_lang_for_flask()
    agents = smon_sql.get_agents(g.user_params['group_id'])
    return render_template('ajax/smon/check.html', smon=smon, lang=lang, check_type_id=check_type_id, agents=agents)


@bp.get('/checks/count')
@login_required
def get_checks_count():
    try:
        smon_mod.check_checks_limit()
    except Exception as e:
        return f'{e}'

    return 'ok'


@bp.post('/checks/move')
@login_required
def move_checks():
    old_agent = int(request.json.get('old_agent'))
    new_agent = int(request.json.get('new_agent'))
    old_agent_ip = smon_sql.get_agent_ip_by_id(old_agent)
    # new_agent_ip = smon_sql.get_agent_ip_by_id(new_agent)
    checks = {}

    try:
        for check_type in ('http', 'tcp', 'dns', 'ping'):
            got_checks = smon_sql.select_checks_for_agent(old_agent, check_type)
            for c in got_checks:
                print(c.smon_id)
                checks[c.smon_id] = check_type
                agent_mod.delete_check(old_agent, old_agent_ip, c.smon_id)
                smon_sql.update_check_agent(c.smon_id, new_agent, check_type)
    except Exception as e:
        roxywi_common.handle_json_exceptions(e, f'Cannot get checks')

    agent_mod.send_checks(new_agent)

    return jsonify({'checks': str(checks)})

