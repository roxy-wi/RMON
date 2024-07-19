import json

from flask import render_template
from flask_jwt_extended import get_jwt
from flask_jwt_extended import verify_jwt_in_request

import app.modules.db.sql as sql
import app.modules.db.roxy as roxy_sql
import app.modules.db.user as user_sql
import app.modules.db.smon as smon_sql
import app.modules.db.server as server_sql
import app.modules.tools.common as tools_common
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.smon_agent as smon_agent


def user_owv() -> str:
    lang = roxywi_common.get_user_lang_for_flask()
    roles = sql.select_roles()
    user_params = roxywi_common.get_users_params()
    users_groups = user_sql.select_user_groups_with_names(1, all=1)
    user_group = roxywi_common.get_user_group(id=1)

    if (user_params['role'] == 2 or user_params['role'] == 3) and int(user_group) != 1:
        users = user_sql.select_users(group=user_group)
    else:
        users = user_sql.select_users()

    return render_template('ajax/show_users_ovw.html', users=users, users_groups=users_groups, lang=lang, roles=roles)


def show_sub_ovw() -> str:
    lang = roxywi_common.get_user_lang_for_flask()

    return render_template('ajax/show_sub_ovw.html', sub=roxy_sql.select_user_all(), lang=lang)


def show_services_overview():
    user_params = roxywi_common.get_users_params()
    servers_group = []
    user_group = roxywi_common.get_user_group(id=1)
    lang = roxywi_common.get_user_lang_for_flask()

    if (user_params['role'] == 2 or user_params['role'] == 3) and int(user_group) != 1:
        for s in user_params['servers']:
            servers_group.append(s[2])

    roxy_tools = roxy_sql.get_roxy_tools()
    roxy_tools_status = {}
    for tool in roxy_tools:
        status = tools_common.is_tool_active(tool)
        roxy_tools_status.setdefault(tool, status)

    return render_template(
        'ajax/show_services_ovw.html', role=user_params['role'], roxy_tools_status=roxy_tools_status, lang=lang
    )


def show_overview(server_ip) -> str:
    servers_sorted = []
    verify_jwt_in_request()
    claims = get_jwt()
    lang = roxywi_common.get_user_lang_for_flask()
    role = user_sql.get_user_role_in_group(claims['user_id'], claims['group'])
    server_name = server_sql.get_hostname_by_server_ip(server_ip)
    try:
        agent_id = smon_sql.get_agent_id_by_ip(server_ip)
    except Exception:
        agent_id = 0

    try:
        req = smon_agent.send_get_request_to_agent(agent_id, server_ip, 'scheduler')
        req = json.loads(req.decode('utf-8'))
    except Exception:
        req = {'running': False}

    servers_sorted.append(server_ip)
    servers_sorted.append(server_name)
    servers_sorted.append(agent_id)
    servers_sorted.append(req)
    return render_template('ajax/overview.html', service_status=servers_sorted, role=role, lang=lang)
