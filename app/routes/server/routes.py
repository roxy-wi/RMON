from flask import render_template, request
from flask_login import login_required

from app.routes.server import bp
import app.modules.db.cred as cred_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
import app.modules.common.common as common
import app.modules.roxywi.group as group_mod
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
import app.modules.server.ssh as ssh_mod
import app.modules.server.server as server_mod
import app.modules.tools.smon as smon_mod
from app.middleware import get_user_params

error_mess = roxywi_common.return_error_message()


@bp.before_request
@login_required
def before_request():
    """ Protect all the admin endpoints. """
    pass


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


@bp.post('/create')
@get_user_params()
def create_server():
    roxywi_auth.page_for_admin(level=2)
    hostname = common.checkAjaxInput(request.form.get('servername'))
    ip = common.is_ip_or_dns(request.form.get('newip'))
    group = common.checkAjaxInput(request.form.get('newservergroup'))
    enable = common.checkAjaxInput(request.form.get('enable'))
    cred = common.checkAjaxInput(request.form.get('cred'))
    page = common.checkAjaxInput(request.form.get('page'))
    page = page.split("#")[0]
    port = common.checkAjaxInput(request.form.get('newport'))
    desc = common.checkAjaxInput(request.form.get('desc'))
    add_to_smon = common.checkAjaxInput(request.form.get('add_to_smon'))
    lang = roxywi_common.get_user_lang_for_flask()

    if ip == '':
        return 'error: IP or DNS name is not valid'
    try:
        if server_mod.create_server(hostname, ip, group, enable, cred, port, desc):
            if add_to_smon:
                try:
                    user_group = roxywi_common.get_user_group(id=1)
                    json_data = {
                        "name": hostname,
                        "ip": ip,
                        "port": "0",
                        "enabled": "1",
                        "url": "",
                        "body": "",
                        "group": hostname,
                        "desc": f"Ping {hostname}",
                        "tg": "0",
                        "slack": "0",
                        "pd": "0",
                        "resolver": "",
                        "record_type": "",
                        "packet_size": "56",
                        "http_method": "",
                        "check_type": "ping",
                        "agent_id": "1",
                        "interval": "120",
                    }
                    smon_mod.create_smon(json_data, user_group)
                except Exception as e:
                    roxywi_common.logging(ip, f'error: Cannot add server {hostname} to SMON: {e}')

            roxywi_common.logging(ip, f'A new server {hostname} has been created', login=1, keep_history=1, service='server')

            return render_template(
                'ajax/new_server.html', groups=group_sql.select_groups(), servers=server_sql.select_servers(server=ip), lang=lang,
                sshs=cred_sql.select_ssh(group=group), page=page, adding=1
            )
    except Exception as e:
        return f'{e}'


@bp.post('/create/after')
def after_add():
    hostname = common.checkAjaxInput(request.form.get('servername'))
    ip = common.is_ip_or_dns(request.form.get('newip'))

    try:
        return server_mod.update_server_after_creating(hostname, ip)
    except Exception as e:
        return str(e)


@bp.post('/update')
def update_server():
    roxywi_auth.page_for_admin(level=2)
    name = request.form.get('updateserver')
    group = request.form.get('servergroup')
    enable = request.form.get('enable')
    serv_id = int(request.form.get('id'))
    cred = request.form.get('cred')
    port = request.form.get('port')
    desc = request.form.get('desc')

    if name is None or port is None:
        return error_mess
    else:
        server_sql.update_server(name, group, enable, serv_id, cred, port, desc)
        server_ip = server_sql.select_server_ip_by_id(serv_id)
        roxywi_common.logging(server_ip, f'The server {name} has been update', roxywi=1, login=1, keep_history=1, service='server')

    return 'ok'


@bp.route('/delete/<int:server_id>')
def delete_server(server_id):
    roxywi_auth.page_for_admin(level=2)
    return server_mod.delete_server(server_id)


@bp.route('/group/create', methods=['POST'])
def create_group():
    roxywi_auth.page_for_admin()
    newgroup = common.checkAjaxInput(request.form.get('groupname'))
    desc = common.checkAjaxInput(request.form.get('newdesc'))
    if newgroup == '':
        return error_mess
    else:
        try:
            if group_sql.add_group(newgroup, desc):
                roxywi_common.logging('RMON server', f'A new group {newgroup} has been created', roxywi=1, login=1)
                return render_template('ajax/new_group.html', groups=group_sql.select_groups(group=newgroup))
        except Exception as e:
            return str(e)


@bp.route('/group/update', methods=['POST'])
def update_group():
    roxywi_auth.page_for_admin()
    name = common.checkAjaxInput(request.form.get('updategroup'))
    desc = common.checkAjaxInput(request.form.get('descript'))
    group_id = common.checkAjaxInput(request.form.get('id'))

    return group_mod.update_group(group_id, name, desc)


@bp.route('/group/delete/<int:group_id>')
def delete_group(group_id):
    roxywi_auth.page_for_admin()
    return group_mod.delete_group(group_id)


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
