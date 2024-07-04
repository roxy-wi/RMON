from flask.views import MethodView
from flask_pydantic import validate
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
from app.middleware import get_user_params, page_for_admin, check_group
from app.modules.roxywi.exception import RoxywiGroupMismatch, RoxywiResourceNotFound
from app.modules.roxywi.class_models import BaseResponse, IdResponse, ServerRequest, GroupQuery


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
        if request.method not in ('GET', 'DELETE'):
            self.json_data = request.get_json()
        else:
            self.json_data = None
        self.is_api = is_api

    @validate(query=GroupQuery)
    def get(self, server_id: int, query: GroupQuery):
        """
        Retrieve server information based on GroupQuery
        ---
        tags:
          - 'Server'
        parameters:
          - in: 'query'
            name: 'GroupQuery'
            description: 'GroupQuery to filter servers. Only for superAdmin role'
            required: false
            schema:
              type: 'string'
        responses:
          200:
            description: 'Server Information'
            content:
              application/json:
                schema:
                  type: 'object'
                  properties:
                    alert:
                      type: 'integer'
                      description: 'Alert status of the server'
                    creds_id:
                      type: 'integer'
                      description: 'Credentials ID'
                    desc:
                      type: 'string'
                      description: 'Description of the server'
                    enabled:
                      type: 'integer'
                      description: 'Enabled status of the server'
                    group_id:
                      type: 'string'
                      description: 'ID of the group the server belongs to'
                    hostname:
                      type: 'string'
                      description: 'Hostname of the server'
                    ip:
                      type: 'string'
                      description: 'IP address of the server'
                    port:
                      type: 'integer'
                      description: 'Port number of the server'
                    pos:
                      type: 'integer'
                      description: 'Position of the server'
                    server_id:
                      type: 'integer'
                      description: 'ID of the server'
        """
        if g.user_params['role'] == 1:
            if query.group_id:
                group_id = query.group_id
            else:
                group_id = g.user_params['group_id']
        else:
            group_id = g.user_params['group_id']
        try:
            server = server_sql.get_server_with_group(server_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get group')
        return jsonify(model_to_dict(server))

    @validate(body=ServerRequest)
    def post(self, body: ServerRequest):
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
                - hostname
                - ip
                - enabled
                - creds_id
                - port
                - desc
              properties:
                hostname:
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
        responses:
          201:
            description: Server creation successful
        """
        if g.user_params['role'] == 1:
            if body.group_id:
                group = body.group_id
            else:
                group = int(g.user_params['group_id'])
        else:
            group = int(g.user_params['group_id'])
        lang = roxywi_common.get_user_lang_for_flask()

        try:
            last_id = server_mod.create_server(body.hostname, body.ip, group, body.enabled, body.creds_id, body.port, body.desc)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create a server')

        roxywi_common.logging(body.ip, f'A new server {body.hostname} has been created', login=1, keep_history=1, service='server')

        try:
            server_mod.update_server_after_creating(body.hostname, body.ip)
        except Exception as e:
            roxywi_common.logging(body.ip, f'error: Cannot get system info from {body.hostname}: {e}', login=1, keep_history=1, service='server')

        if self.is_api:
            return IdResponse(id=last_id).model_dump(mode='json'), 201
        else:
            data = render_template('ajax/new_server.html', groups=group_sql.select_groups(),
                servers=server_sql.select_servers(server=body.ip), lang=lang, sshs=cred_sql.select_ssh(group=group), adding=1)
            return jsonify({'status': 'Created', 'data': data, 'id': last_id}), 201

    @validate(body=ServerRequest)
    def put(self, server_id: int, body: ServerRequest):
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
        if g.user_params['role'] == 1:
            if body.group_id:
                group = body.group_id
            else:
                group = int(g.user_params['group_id'])
        else:
            group = int(g.user_params['group_id'])

        try:
            server_sql.update_server(body.hostname, group, body.enabled, server_id, body.creds_id, body.port, body.desc)
            server_ip = server_sql.select_server_ip_by_id(server_id)
            roxywi_common.logging(server_ip, f'The server {body.hostname} has been update', roxywi=1, login=1, keep_history=1, service='server')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update server')

        return BaseResponse().model_dump(mode='json'), 201

    def delete(self, server_id: int):
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
            server_mod.delete_server(server_id)
            return BaseResponse.model_dump(mode='json'), 204
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
        if request.method not in ('GET', 'DELETE'):
            self.json_data = request.get_json()
        else:
            self.json_data = None
        self.is_api = is_api

    def get(self, group_id: int):
        ...

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
                return IdResponse(id=last_id).model_dump(mode='json'), 201
            else:
                data = render_template('ajax/new_group.html', groups=group_sql.select_groups(group=group))
                return jsonify({'status': 'Created', 'data': data, 'id': last_id}), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create group')

    def put(self, group_id: int):
        """
        Update a group
        ---
        tags:
          - Group
        parameters:
          - in: 'path'
            name: 'group_id'
            description: 'Group ID to change'
            required: true
            schema:
              type: 'integer'
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
        responses:
          201:
            description: Group update successful
       """
        try:
            name = common.checkAjaxInput(self.json_data['name'])
            desc = common.checkAjaxInput(self.json_data['desc'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse group data')

        try:
            group_mod.update_group(group_id, name, desc)
            return jsonify({'status': 'Created'}), 201
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot update group')

    def delete(self, group_id: int):
        """
        Delete a group
        ---
        tags:
          - Group
        parameters:
          - in: 'path'
            name: 'group_id'
            description: 'Group ID to delete'
            required: true
            schema:
              type: 'integer'
        responses:
          204:
            description: Group deletion successful
        """
        try:
            self._check_is_user_and_group(group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user or group'), 404
        try:
            group_mod.delete_group(group_id)
            return jsonify({'status': 'Ok'}), 204
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot delete group')

    @staticmethod
    def _check_is_user_and_group(group_id: int):
        try:
            groups = group_sql.get_group_name_by_id(group_id)
            if len(groups) == 0:
                raise RoxywiResourceNotFound
        except Exception as e:
            raise e


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
