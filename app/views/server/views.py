from flask.views import MethodView
from flask_pydantic import validate
from flask_jwt_extended import jwt_required
from flask import render_template, jsonify
from playhouse.shortcuts import model_to_dict

import app.modules.db.cred as cred_sql
import app.modules.db.group as group_sql
import app.modules.db.server as server_sql
import app.modules.roxywi.group as group_mod
import app.modules.roxywi.common as roxywi_common
import app.modules.server.server as server_mod
from app.middleware import get_user_params, page_for_admin, check_group
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.roxywi.class_models import BaseResponse, IdResponse, IdDataResponse, ServerRequest, GroupQuery, GroupRequest
from app.modules.common.common_classes import SupportClass


class ServerView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE"]

    def __init__(self, is_api=False):
        super().__init__()
        self.is_api = is_api

    @validate(query=GroupQuery)
    def get(self, server_id: int, query: GroupQuery):
        """
        Retrieve server information based on GroupQuery
        ---
        tags:
          - 'Server'
        parameters:
          - in: 'path'
            name: 'server_id'
            description: 'ID of the User to retrieve'
            required: true
            type: 'integer'
          - in: 'query'
            name: 'GroupQuery'
            description: 'GroupQuery to filter servers. Only for superAdmin role'
            required: false
            type: 'integer'
        responses:
          200:
            description: 'Server Information'
            schema:
              type: 'object'
              properties:
                alert:
                  type: 'integer'
                  description: 'Alert status of the server'
                cred_id:
                  type: 'integer'
                  description: 'Credentials ID'
                description:
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
        group_id = SupportClass.return_group_id(query)
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
                - cred_id
                - port
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
                cred_id:
                  type: integer
                  description: The ID of the credentials
                port:
                  type: integer
                  description: The port number
                description:
                  type: string
                  description: The server description
        responses:
          201:
            description: Server creation successful
        """
        group_id = SupportClass.return_group_id(body)

        try:
            last_id = server_mod.create_server(body.hostname, body.ip, group_id, body.enabled, body.cred_id, body.port, body.description)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create a server')

        roxywi_common.logging(body.ip, f'A new server {body.hostname} has been created', login=1, keep_history=1, service='server')
        try:
            server_mod.update_server_after_creating(body.hostname, body.ip)
        except Exception as e:
            roxywi_common.logging(body.ip, f'Cannot get system info from {body.hostname}: {e}', login=1, keep_history=1, service='server', mes_type='error')

        if self.is_api:
            return IdResponse(id=last_id).model_dump(mode='json'), 201
        else:
            lang = roxywi_common.get_user_lang_for_flask()
            data = render_template('ajax/new_server.html', groups=group_sql.select_groups(),
                servers=server_sql.select_servers(server=body.ip), lang=lang, sshs=cred_sql.select_ssh(group=group_id), adding=1)
            return IdDataResponse(data=data, id=last_id), 201

    @validate(body=ServerRequest)
    def put(self, server_id: int, body: ServerRequest):
        """
        Update a server
        ---
        tags:
          - Server
        parameters:
          - in: 'path'
            name: 'server_id'
            description: 'ID of the User to retrieve'
            required: true
            type: 'integer'
          - in: body
            name: body
            schema:
              id: UpdateServer
              required:
                - name
                - enabled
                - cred_id
                - port
              properties:
                name:
                  type: string
                  description: The server name
                enabled:
                  type: integer
                  description: If server is enabled or not
                cred_id:
                  type: integer
                  description: The ID of the credentials
                port:
                  type: integer
                  description: The port number
                description:
                  type: string
                  description: The server description
        responses:
          201:
            description: Server update successful
       """
        group_id = SupportClass.return_group_id(body)

        try:
            server_sql.update_server(body.hostname, group_id, body.enabled, server_id, body.cred_id, body.port, body.description)
            server_ip = server_sql.select_server_ip_by_id(server_id)
            roxywi_common.logging(server_ip, f'The server {body.hostname} has been update', roxywi=1, login=1, keep_history=1, service='server')
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update server')

        return BaseResponse().model_dump(mode='json'), 201

    @staticmethod
    def delete(server_id: int):
        """
        Delete a server
        ---
        tags:
          - Server
        parameters:
          - in: 'path'
            name: 'server_id'
            description: 'ID of the User to retrieve'
            required: true
            type: 'integer'
        responses:
          204:
            description: Server deletion successful
        """
        try:
            server_mod.delete_server(server_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete server')


class ServersView(MethodView):
    methods = ["GET"]
    decorators = [get_user_params(), page_for_admin(level=2), check_group()]

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Retrieve servers information based on GroupQuery
        ---
        tags:
          - 'Server'
        parameters:
          - in: 'query'
            name: 'GroupQuery'
            description: 'GroupQuery to filter servers. Only for superAdmin role'
            required: false
            type: 'integer'
        responses:
          200:
            description: 'Servers Information'
            schema:
              type: 'array'
              items:
                type: 'object'
                properties:
                  alert:
                    type: 'integer'
                  cred_id:
                    type: 'integer'
                  description:
                    type: 'string'
                  enabled:
                    type: 'integer'
                  group_id:
                    type: 'integer'
                  hostname:
                    type: 'string'
                  ip:
                    type: 'string'
                  port:
                    type: 'integer'
                  pos:
                    type: 'integer'
                  server_id:
                    type: 'integer'
          default:
            description: Unexpected error
        """
        group_id = SupportClass.return_group_id(query)
        try:
            servers = server_sql.select_servers_with_group(group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get group')
        servers_list = [model_to_dict(server) for server in servers]
        return jsonify(servers_list)


class ServerGroupView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin()]

    def get(self, group_id: int):
        """
        Retrieve group information for a specific group_id
        ---
        tags:
          - 'Group'
        parameters:
          - in: 'path'
            name: 'group_id'
            description: 'ID of the group to retrieve to get the group'
            required: true
            type: 'integer'
        responses:
          200:
            description: 'Group Information'
            schema:
              type: 'object'
              properties:
                description:
                  type: 'string'
                  description: 'Description of the server group'
                group_id:
                  type: 'integer'
                  description: 'Server group ID'
                name:
                  type: 'string'
                  description: 'Name of the server group'
          404:
            description: 'Server group not found'
        """
        try:
            groups = group_sql.select_groups(id=group_id)
            for group in groups:
                return model_to_dict(group)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get group')

    @validate(body=GroupRequest)
    def post(self, body: GroupRequest):
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
              properties:
                name:
                  type: string
                  description: The group name
                description:
                  type: string
                  description: The group description
        responses:
          201:
            description: Group creation successful
        """
        try:
            last_id = group_sql.add_group(body.name, body.description)
            roxywi_common.logging('RMON server', f'A new group {body.name} has been created', roxywi=1, login=1)
            return IdResponse(id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create group')

    @validate(body=GroupRequest)
    def put(self, group_id: int, body: GroupRequest):
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
            type: 'integer'
          - in: body
            name: body
            schema:
              id: UpdateGroup
              required:
                - name
                - id
              properties:
                name:
                  type: string
                  description: The group name
                description:
                  type: string
                  description: The group description
        responses:
          201:
            description: Group update successful
       """

        try:
            group_mod.update_group(group_id, body.name, body.description)
            return BaseResponse(), 201
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
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot delete group')

    @staticmethod
    def _check_is_user_and_group(group_id: int):
        try:
            groups = group_sql.get_group_name_by_id(group_id)
            if len(groups) == 0:
                raise RoxywiResourceNotFound
        except Exception as e:
            raise e


class ServerGroupsView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), page_for_admin()]

    def get(self):
        """
        This endpoint allows to get server groups.
        ---
        tags:
          - Group
        responses:
          200:
            description: Server groups retrieved successfully
            schema:
              type: array
              items:
                type: object
                properties:
                  description:
                    type: string
                  group_id:
                    type: integer
                  name:
                    type: string
          default:
            description: Unexpected error
        """
        groups_list = []
        groups = group_sql.select_groups()
        for group in groups:
            groups_list.append(model_to_dict(group))
        return jsonify(groups_list)
