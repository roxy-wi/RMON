from flask import jsonify
from flask_jwt_extended import jwt_required
from flask_pydantic import validate
from pydantic import IPvAnyAddress

from app.routes.server import bp
import app.modules.db.server as server_sql
import app.modules.common.common as common
import app.modules.roxywi.auth as roxywi_auth
import app.modules.server.server as server_mod
from app.views.server.views import ServerView
from app.views.server.cred_views import CredView


@bp.before_request
@jwt_required()
def before_request():
    """ Protect all the admin endpoints. """
    pass


bp.add_url_rule('', view_func=ServerView.as_view('server'), methods=['POST'])
bp.add_url_rule('/cred', view_func=CredView.as_view('cred'), methods=['POST'])


@bp.route('/check/ssh/<server_ip>')
@validate()
def check_ssh(server_ip: IPvAnyAddress):
    roxywi_auth.page_for_admin(level=2)

    try:
        return server_mod.ssh_command(str(server_ip), "ls -1t")
    except Exception as e:
        return str(e)


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
        'desc': server.description.replace("'", ""),
        'ip': server.ip,
        'port': server.port,
        'enabled': server.enabled,
        'cred_id': server.cred_id,
        'group_id': server.group_id
    }
    return jsonify(status)


@bp.app_template_filter('string_to_dict')
def string_to_dict(dict_string) -> dict:
    from ast import literal_eval
    return literal_eval(dict_string)


@bp.route('/system_info/get/<server_ip>/<int:server_id>')
@validate()
def get_system_info(server_ip: IPvAnyAddress, server_id: int):
    return server_mod.show_system_info(str(server_ip), server_id)


@bp.route('/system_info/update/<server_ip>/<int:server_id>')
@validate()
def update_system_info(server_ip: IPvAnyAddress, server_id: int):
    return server_mod.update_system_info(str(server_ip), server_id)


@bp.route('/firewall/<server_ip>')
@validate()
def show_firewall(server_ip: IPvAnyAddress):
    roxywi_auth.page_for_admin(level=2)

    return server_mod.show_firewalld_rules(str(server_ip))
