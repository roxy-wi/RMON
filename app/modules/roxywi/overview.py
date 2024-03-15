import psutil
from flask import render_template, request

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
    grafana = 0
    metrics_worker = 0
    checker_worker = 0
    servers_group = []
    host = request.host
    user_group = roxywi_common.get_user_group(id=1)
    lang = roxywi_common.get_user_lang_for_flask()

    if (user_params['role'] == 2 or user_params['role'] == 3) and int(user_group) != 1:
        for s in user_params['servers']:
            servers_group.append(s[2])

    is_checker_worker = 0
    is_metrics_worker = 0

    for pids in psutil.pids():
        if pids < 300:
            continue
        try:
            pid = psutil.Process(pids)
            cmdline_out = pid.cmdline()
            if len(cmdline_out) > 2:
                if 'checker_' in cmdline_out[1]:
                    if len(servers_group) > 0:
                        if cmdline_out[2] in servers_group:
                            checker_worker += 1
                    else:
                        checker_worker += 1
                elif 'metrics_' in cmdline_out[1]:
                    if len(servers_group) > 0:
                        if cmdline_out[2] in servers_group:
                            metrics_worker += 1
                    else:
                        metrics_worker += 1
                if len(servers_group) == 0:
                    if 'grafana' in cmdline_out[1]:
                        grafana += 1
        except psutil.NoSuchProcess:
            pass

    roxy_tools = roxy_sql.get_roxy_tools()
    roxy_tools_status = {}
    for tool in roxy_tools:
        status = tools_common.is_tool_active(tool)
        roxy_tools_status.setdefault(tool, status)

    return render_template(
        'ajax/show_services_ovw.html', role=user_params['role'], roxy_tools_status=roxy_tools_status, grafana=grafana,
        is_checker_worker=is_checker_worker, is_metrics_worker=is_metrics_worker, host=host,
        checker_worker=checker_worker, metrics_worker=metrics_worker, lang=lang
    )
