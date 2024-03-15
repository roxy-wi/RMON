from flask import render_template

import app.modules.db.sql as sql
import app.modules.db.roxy as roxy_sql
import app.modules.db.user as user_sql
import app.modules.tools.common as tools_common
import app.modules.roxywi.common as roxywi_common


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
