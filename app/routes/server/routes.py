import json
import time

from flask import Response, stream_with_context, jsonify
from flask_jwt_extended import jwt_required

from app.routes.server import bp
import app.modules.db.server as server_sql
import app.modules.common.common as common
import app.modules.roxywi.auth as roxywi_auth
import app.modules.server.server as server_mod
from app.views.server.views import ServerView, CredView


@bp.before_request
@jwt_required()
def before_request():
    """ Protect all the admin endpoints. """
    pass


bp.add_url_rule('', view_func=ServerView.as_view('server'), methods=['POST'])
bp.add_url_rule('/cred', view_func=CredView.as_view('cred'), methods=['POST'])


@bp.route('/check/ssh/<server_ip>')
def check_ssh(server_ip):
    roxywi_auth.page_for_admin(level=2)
    server_ip = common.is_ip_or_dns(server_ip)

    try:
        return server_mod.ssh_command(server_ip, "ls -1t")
    except Exception as e:
        return str(e)


# @bp.route('/check/server/<int:server_id>')
# def check_server(server_id):
#     def get_check():
#         while True:
#             try:
#                 server = server_sql.get_server(server_id)
#             except Exception as e:
#                 raise e
#             result = server_mod.server_is_up(server.ip)
#             status = {
#                 "status": result,
#                 'name': server.hostname.replace("'", ""),
#                 'desc': server.desc.replace("'", ""),
#                 'ip': server.ip,
#                 'port': server.port,
#                 'enabled': server.enabled,
#                 'creds_id': server.creds_id,
#                 'group_id': server.group_id
#             }
#             yield f'data:{json.dumps(status)}\n\n'
#             time.sleep(60)
#
#     response = Response(stream_with_context(get_check()), mimetype="text/event-stream")
#     response.headers["Cache-Control"] = "no-cache"
#     response.headers["X-Accel-Buffering"] = "no"
#     return response@bp.route('/check/server/<int:server_id>')


@bp.route('/check/server/<int:server_id>')
def check_server(server_id):
    try:
        server = server_sql.get_server(server_id)
    except Exception as e:
        raise e
    result = server_mod.server_is_up(server.ip)
    status = {
        "status": result,
        'name': server.hostname.replace("'", ""),
        'desc': server.desc.replace("'", ""),
        'ip': server.ip,
        'port': server.port,
        'enabled': server.enabled,
        'creds_id': server.creds_id,
        'group_id': server.group_id
    }
    return jsonify(status)


@bp.route('/show/if/<server_ip>')
def show_if(server_ip):
    roxywi_auth.page_for_admin(level=2)
    server_ip = common.is_ip_or_dns(server_ip)
    command = "sudo ip link|grep 'UP' |grep -v 'lo'| awk '{print $2}' |awk -F':' '{print $1}'"

    return server_mod.ssh_command(server_ip, command)


@bp.app_template_filter('string_to_dict')
def string_to_dict(dict_string) -> dict:
    from ast import literal_eval
    return literal_eval(dict_string)


@bp.route('/system_info/get/<server_ip>/<int:server_id>')
def get_system_info(server_ip, server_id):
    server_ip = common.is_ip_or_dns(server_ip)

    return server_mod.show_system_info(server_ip, server_id)


@bp.route('/system_info/update/<server_ip>/<int:server_id>')
def update_system_info(server_ip, server_id):
    server_ip = common.is_ip_or_dns(server_ip)

    return server_mod.update_system_info(server_ip, server_id)


@bp.route('/firewall/<server_ip>')
def show_firewall(server_ip):
    roxywi_auth.page_for_admin(level=2)

    server_ip = common.is_ip_or_dns(server_ip)

    return server_mod.show_firewalld_rules(server_ip)
