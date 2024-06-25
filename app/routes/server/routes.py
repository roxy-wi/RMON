from flask import request
from flask_jwt_extended import jwt_required

from app.routes.server import bp
import app.modules.common.common as common
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
import app.modules.server.ssh as ssh_mod
import app.modules.server.server as server_mod
from app.views.server.views import ServerView, GroupView

error_mess = roxywi_common.return_error_message()


@bp.before_request
@jwt_required()
def before_request():
    """ Protect all the admin endpoints. """
    pass


bp.add_url_rule('', view_func=ServerView.as_view('server'))
bp.add_url_rule('/group', view_func=GroupView.as_view('group'))


@bp.route('/check/ssh/<server_ip>')
def check_ssh(server_ip):
    roxywi_auth.page_for_admin(level=2)
    server_ip = common.is_ip_or_dns(server_ip)

    try:
        return server_mod.ssh_command(server_ip, "ls -1t")
    except Exception as e:
        return str(e)


@bp.route('/check/server/<server_ip>')
def check_server(server_ip):
    server_ip = common.is_ip_or_dns(server_ip)

    return server_mod.server_is_up(server_ip)


@bp.route('/show/if/<server_ip>')
def show_if(server_ip):
    roxywi_auth.page_for_admin(level=2)
    server_ip = common.is_ip_or_dns(server_ip)
    command = "sudo ip link|grep 'UP' |grep -v 'lo'| awk '{print $2}' |awk -F':' '{print $1}'"

    return server_mod.ssh_command(server_ip, command)


@bp.route('/ssh/create', methods=['POST'])
def create_ssh():
    roxywi_auth.page_for_admin(level=2)
    return ssh_mod.create_ssh_cred()


@bp.route('/ssh/delete/<int:ssh_id>')
def delete_ssh(ssh_id):
    roxywi_auth.page_for_admin(level=2)
    return ssh_mod.delete_ssh_key(ssh_id)


@bp.route('/ssh/update', methods=['POST'])
def update_ssh():
    roxywi_auth.page_for_admin(level=2)
    return ssh_mod.update_ssh_key()


@bp.route('/ssh/upload', methods=['POST'])
def upload_ssh_key():
    user_group = roxywi_common.get_user_group()
    name = common.checkAjaxInput(request.form.get('name'))
    passphrase = common.checkAjaxInput(request.form.get('pass'))
    key = request.form.get('ssh_cert')

    try:
        return ssh_mod.upload_ssh_key(name, user_group, key, passphrase)
    except Exception as e:
        return str(e)


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
