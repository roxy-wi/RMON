from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import render_template, jsonify, request

import app.modules.db.cred as cred_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
import app.modules.common.common as common
import app.modules.roxywi.group as group_mod
import app.modules.roxywi.common as roxywi_common
import app.modules.server.server as server_mod
import app.modules.tools.smon as smon_mod
from app.middleware import get_user_params, page_for_admin


class ServerView(MethodView):
    methods = ["POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2)]

    def __init__(self, is_api=False):
        self.json_data = request.get_json()
        self.is_api = is_api

    def post(self):
        try:
            hostname = common.checkAjaxInput(self.json_data['name'])
            ip = common.is_ip_or_dns(self.json_data['ip'])
            group = int(self.json_data['group'])
            enable = int(self.json_data['enabled'])
            cred = int(self.json_data['creds_id'])
            port = int(self.json_data['port'])
            desc = common.checkAjaxInput(self.json_data['desc'])
            add_to_smon = int(self.json_data['add_to_smon'])
            lang = roxywi_common.get_user_lang_for_flask()
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse server data')

        try:
            last_id = server_mod.create_server(hostname, ip, group, enable, cred, port, desc)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create a server')

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

        try:
            server_mod.update_server_after_creating(hostname, ip)
        except Exception as e:
            roxywi_common.logging(ip, f'error: Cannot get system info from {hostname}: {e}', login=1, keep_history=1, service='server')

        if self.is_api:
            return jsonify({'status': 'created', 'id': last_id}), 201
        else:
            data = render_template('ajax/new_server.html', groups=group_sql.select_groups(),
                servers=server_sql.select_servers(server=ip), lang=lang, sshs=cred_sql.select_ssh(group=group), adding=1)
            return jsonify({'status': 'created', 'data': data, 'id': last_id}), 201

    def put(self):
        try:
            name = common.checkAjaxInput(self.json_data['name'])
            group = int(self.json_data['group'])
            enable = int(self.json_data['enabled'])
            serv_id = int(self.json_data['server_id'])
            cred = int(self.json_data['creds_id'])
            port = int(self.json_data['port'])
            desc = common.checkAjaxInput(self.json_data['desc'])
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse server data')

        try:
            server_sql.update_server(name, group, enable, serv_id, cred, port, desc)
            server_ip = server_sql.select_server_ip_by_id(serv_id)
            roxywi_common.logging(server_ip, f'The server {name} has been update', roxywi=1, login=1, keep_history=1, service='server')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update server')

        return jsonify({'status': 'updated'})

    def delete(self):
        server_id = int(self.json_data['server_id'])
        try:
            server_mod.delete_server(server_id)
            return jsonify({'status': 'deleted'})
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete server')


class GroupView(MethodView):
    methods = ["POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin()]

    def __init__(self, is_api=False):
        self.json_data = request.get_json()
        self.is_api = is_api

    def post(self):
        try:
            group = common.checkAjaxInput(self.json_data['name'])
            desc = common.checkAjaxInput(self.json_data['desc'])
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse group data')
        try:
            last_id = group_sql.add_group(group, desc)
            roxywi_common.logging('RMON server', f'A new group {group} has been created', roxywi=1, login=1)
            if self.is_api:
                return jsonify({'status': 'created', 'id': last_id}), 201
            else:
                data = render_template('ajax/new_group.html', groups=group_sql.select_groups(group=group))
                return jsonify({'status': 'created', 'data': data, 'id': last_id}), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create group')

    def put(self):
        try:
            name = common.checkAjaxInput(self.json_data['name'])
            desc = common.checkAjaxInput(self.json_data['desc'])
            group_id = int(self.json_data['group_id'])
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse group data')

        try:
            group_mod.update_group(group_id, name, desc)
            return jsonify({'status': 'updated'})
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot update group')

    def delete(self):
        try:
            group_id = int(self.json_data['group_id'])
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse group data')
        try:
            group_mod.delete_group(group_id)
            return jsonify({'status': 'deleted'})
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot delete group')
