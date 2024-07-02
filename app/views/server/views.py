from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import render_template, jsonify, request, g
from playhouse.shortcuts import model_to_dict

from app.modules.db.db_model import Cred
import app.modules.db.cred as cred_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
import app.modules.common.common as common
import app.modules.roxywi.group as group_mod
import app.modules.roxywi.common as roxywi_common
import app.modules.server.ssh as ssh_mod
import app.modules.server.server as server_mod
import app.modules.tools.smon as smon_mod
from app.middleware import get_user_params, page_for_admin, check_group
from app.modules.roxywi.exception import RoxywiGroupMismatch, RoxywiResourceNotFound


class ServerView(MethodView):
    methods = ["POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2), check_group()]

    def __init__(self, is_api=False):
        """
        Initialize ServerView instance
        ---
        parameters:
          - name: is_api
            in: path
            type: boolean
            description: is api
        """
        self.json_data = request.get_json()
        self.is_api = is_api

    def post(self):
        """
        Create a new server
        ---
        tags:
          - Server
        parameters:
          - in: body
            name: body
            schema:
              id: NewServer
              required:
                - name
                - ip
                - enabled
                - creds_id
                - port
                - desc
                - add_to_smon
              properties:
                name:
                  type: string
                  description: The server name
                ip:
                  type: string
                  description: The server IP address
                enabled:
                  type: integer
                  description: If server is enabled or not
                creds_id:
                  type: integer
                  description: The ID of the credentials
                port:
                  type: integer
                  description: The port number
                desc:
                  type: string
                  description: The server description
                add_to_smon:
                  type: integer
                  description: If server is to be added to SMON or not
        responses:
          201:
            description: Server creation successful
        """
        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group'])
            else:
                group = int(g.user_params['group_id'])
            hostname = common.checkAjaxInput(self.json_data['name'])
            ip = common.is_ip_or_dns(self.json_data['ip'])
            enable = int(self.json_data['enabled'])
            cred = int(self.json_data['creds_id'])
            port = int(self.json_data['port'])
            desc = common.checkAjaxInput(self.json_data['desc'])
            add_to_smon = int(self.json_data['add_to_smon'])
            lang = roxywi_common.get_user_lang_for_flask()
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse server data')

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
                smon_mod.create_check(json_data, user_group, show_new=False)
            except Exception as e:
                roxywi_common.logging(ip, f'error: Cannot add server {hostname} to SMON: {e}')

        roxywi_common.logging(ip, f'A new server {hostname} has been created', login=1, keep_history=1, service='server')

        try:
            server_mod.update_server_after_creating(hostname, ip)
        except Exception as e:
            roxywi_common.logging(ip, f'error: Cannot get system info from {hostname}: {e}', login=1, keep_history=1, service='server')

        if self.is_api:
            return jsonify({'status': 'Created', 'id': last_id}), 201
        else:
            data = render_template('ajax/new_server.html', groups=group_sql.select_groups(),
                servers=server_sql.select_servers(server=ip), lang=lang, sshs=cred_sql.select_ssh(group=group), adding=1)
            return jsonify({'status': 'Created', 'data': data, 'id': last_id}), 201

    def put(self):
        """
        Update a server
        ---
        tags:
          - Server
        parameters:
          - in: body
            name: body
            schema:
              id: UpdateServer
              required:
                - name
                - enabled
                - id
                - creds_id
                - port
                - desc
              properties:
                name:
                  type: string
                  description: The server name
                enabled:
                  type: integer
                  description: If server is enabled or not
                id:
                  type: integer
                  description: The server ID to be updated
                creds_id:
                  type: integer
                  description: The ID of the credentials
                port:
                  type: integer
                  description: The port number
                desc:
                  type: string
                  description: The server description
        responses:
          201:
            description: Server update successful
       """
        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group'])
            else:
                group = int(g.user_params['group_id'])
            name = common.checkAjaxInput(self.json_data['name'])
            enable = int(self.json_data['enabled'])
            serv_id = int(self.json_data['id'])
            cred = int(self.json_data['creds_id'])
            port = int(self.json_data['port'])
            desc = common.checkAjaxInput(self.json_data['desc'])
        except ValueError as e:
            return roxywi_common.handle_json_exceptions(e, 'There is must be a value')
        except KeyError as e:
            return roxywi_common.handle_json_exceptions(e, 'There is must be a key')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot parse server data')

        try:
            server_sql.update_server(name, group, enable, serv_id, cred, port, desc)
            server_ip = server_sql.select_server_ip_by_id(serv_id)
            roxywi_common.logging(server_ip, f'The server {name} has been update', roxywi=1, login=1, keep_history=1, service='server')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update server')

        return jsonify({'status': 'Created'}), 201

    def delete(self):
        """
        Delete a server
        ---
        tags:
          - Server
        parameters:
          - in: body
            name: body
            schema:
              id: DeleteServer
              required:
                - id
              properties:
                id:
                  type: integer
                  description: The server ID to be deleted
        responses:
          204:
            description: Server deletion successful
        """
        try:
            server_id = int(self.json_data['id'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse server data')
        try:
            server_mod.delete_server(server_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete server')


class ServerGroupView(MethodView):
    methods = ["POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin()]

    def __init__(self, is_api=False):
        """
        Initialize ServerGroupView instance
        ---
        parameters:
          - name: is_api
            in: path
            type: boolean
            description: is api
        """
        self.json_data = request.get_json()
        self.is_api = is_api

    def post(self):
        """
        Create a new group
        ---
        tags:
          - Group
        parameters:
          - in: body
            name: body
            schema:
              id: NewGroup
              required:
                - name
                - desc
              properties:
                name:
                  type: string
                  description: The group name
                desc:
                  type: string
                  description: The group description
        responses:
          201:
            description: Group creation successful
        """
        try:
            group = common.checkAjaxInput(self.json_data['name'])
            desc = common.checkAjaxInput(self.json_data['desc'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse group data')
        try:
            last_id = group_sql.add_group(group, desc)
            roxywi_common.logging('RMON server', f'A new group {group} has been created', roxywi=1, login=1)
            if self.is_api:
                return jsonify({'status': 'Created', 'id': last_id}), 201
            else:
                data = render_template('ajax/new_group.html', groups=group_sql.select_groups(group=group))
                return jsonify({'status': 'Created', 'data': data, 'id': last_id}), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create group')

    def put(self):
        """
        Update a group
        ---
        tags:
          - Group
        parameters:
          - in: body
            name: body
            schema:
              id: UpdateGroup
              required:
                - name
                - desc
                - id
              properties:
                name:
                  type: string
                  description: The group name
                desc:
                  type: string
                  description: The group description
                id:
                  type: integer
                  description: The ID of the group to be updated
        responses:
          201:
            description: Group update successful
       """
        try:
            name = common.checkAjaxInput(self.json_data['name'])
            desc = common.checkAjaxInput(self.json_data['desc'])
            group_id = int(self.json_data['id'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse group data')

        try:
            group_mod.update_group(group_id, name, desc)
            return jsonify({'status': 'Created'}), 201
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot update group')

    def delete(self):
        """
        Delete a group
        ---
        tags:
          - Group
        parameters:
          - in: body
            name: body
            schema:
              id: DeleteGroup
              required:
                - id
              properties:
                id:
                  type: integer
                  description: The ID of the group to be deleted
        responses:
          204:
            description: Group deletion successful
        """
        try:
            group_id = int(self.json_data['id'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse group data')
        try:
            group_mod.delete_group(group_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot delete group')


class CredsView(MethodView):
    methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2), check_group()]

    def __init__(self, is_api=False):
        """
        Initialize CredsView instance
        ---
        parameters:
          - name: is_api
            in: path
            type: boolean
            description: is api
        """
        self.json_data = request.get_json()
        self.is_api = is_api

    @staticmethod
    def get():
        """
        Retrieve credentials based on the group ID
        ---
        tags:
          - SSH credentials
        responses:
          200:
            description: Credentials retrieval successful
            schema:
              $ref: '#/definitions/Credential'
        """
        group_id = int(g.user_params['group_id'])
        try:
            creds = cred_sql.select_ssh(group=group_id)
            json_data = []
            for cred in creds:
                json_data.append(model_to_dict(cred, exclude=[Cred.password, Cred.passphrase]))
            return jsonify(json_data), 200
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get credentials')

    def post(self):
        """
        Create a new credential entry
        ---
        tags:
          - SSH credentials
        parameters:
          - in: body
            name: body
            schema:
              id: AddCredentials
              required:
                - group
                - name
                - username
                - key_enabled
                - password
              properties:
                group:
                  type: integer
                  description: The group ID
                name:
                  type: string
                  description: The credential name
                username:
                  type: string
                  description: The username
                key_enabled:
                  type: integer
                  description: If key is enabled or not
                password:
                  type: string
                  description: The password
        responses:
          201:
            description: Credential addition successful
        """
        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group'])
            else:
                group = int(g.user_params['group_id'])
            name = common.checkAjaxInput(self.json_data['name'])
            username = common.checkAjaxInput(self.json_data['username'])
            enabled = int(self.json_data['key_enabled'])
            try:
                password = common.checkAjaxInput(self.json_data['password'])
            except KeyError:
                password = ''
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse cred data')

        try:
            return ssh_mod.create_ssh_cred(name, password, group, username, enabled, self.is_api)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create new cred')

    def put(self):
        """
        Update a credential entry
        ---
        tags:
          - SSH credentials
        parameters:
          - in: body
            name: body
            schema:
              id: UpdateCredentials
              required:
                - group
                - name
                - username
                - key_enabled
                - id
                - password
              properties:
                group:
                  type: integer
                  description: The group ID
                name:
                  type: string
                  description: The credential name
                username:
                  type: string
                  description: The username
                key_enabled:
                  type: integer
                  description: If key is enabled or not
                id:
                  type: integer
                  description: The SSH ID
                password:
                  type: string
                  description: The password
        responses:
          201:
            description: Credential update successful
        """
        try:
            self._check_is_correct_group()
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, ''), 404

        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group'])
            else:
                group = int(g.user_params['group_id'])
            name = common.checkAjaxInput(self.json_data['name'])
            username = common.checkAjaxInput(self.json_data['username'])
            key_enabled = int(self.json_data['key_enabled'])
            ssh_id = int(self.json_data['id'])
            try:
                password = common.checkAjaxInput(self.json_data['password'])
            except KeyError:
                password = ''
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse cred data')

        try:
            ssh_mod.update_ssh_key(ssh_id, name, password, key_enabled, username, group)
            return jsonify({'status': 'Ok'}), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update SSH key')

    def delete(self):
        """
        Delete a credential entry
        ---
        tags:
          - SSH credentials
        parameters:
          - in: body
            name: body
            schema:
              id: DeleteCredentials
              required:
                - id
              properties:
                id:
                  type: integer
                  description: The SSH ID
        responses:
          204:
            description: Credential deletion successful
        """
        try:
            self._check_is_correct_group()
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, ''), 404

        try:
            ssh_id = int(self.json_data['id'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse cred data')

        try:
            ssh_mod.delete_ssh_key(ssh_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete SSH key')

    def patch(self):
        """
        Upload an SSH private key
        ---
        tags:
          - SSH credentials
        parameters:
         - in: body
           name: body
           schema:
             id: UploadSSHKey
             required:
               - private_key
               - id
               - passphrase
             properties:
               private_key:
                 type: string
                 description: The private key string
               id:
                 type: integer
                 description: The SSH ID
               passphrase:
                 type: string
                 description: The passphrase
        responses:
          201:
            description: SSH key upload successful
        """
        try:
            self._check_is_correct_group()
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, ''), 404

        try:
            key = common.checkAjaxInput(self.json_data['private_key'])
            ssh_id = common.checkAjaxInput(self.json_data['id'])
            try:
                passphrase = common.checkAjaxInput(self.json_data['passphrase'])
            except KeyError:
                passphrase = ''
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse cred data')

        try:
            ssh_mod.upload_ssh_key(ssh_id, key, passphrase)
            return jsonify({'status': 'Ok'}), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot upload SSH key')

    def _check_is_correct_group(self):
        if g.user_params['role'] == 1:
            return True
        try:
            ssh = cred_sql.get_ssh(self.json_data['id'])
        except RoxywiResourceNotFound:
            raise RoxywiResourceNotFound
        if ssh.group_id != g.user_params['group_id']:
            raise RoxywiGroupMismatch
