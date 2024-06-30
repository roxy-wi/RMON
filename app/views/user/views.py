from typing import Union

from flask.views import MethodView
from flask_pydantic import validate
from flask_jwt_extended import jwt_required
from flask import render_template, jsonify, request, g
from playhouse.shortcuts import model_to_dict

import app.modules.db.sql as sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.roxywi.user as roxywi_user
import app.modules.roxywi.common as roxywi_common
from app.modules.db.db_model import User as User_DB
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.roxywi.class_models import UserPost, UserPut, IdResponse, IdDataResponse, BaseResponse, AddUserToGroup
from app.middleware import get_user_params, page_for_admin, check_group


class UserView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2), check_group()]

    def __init__(self, is_api=False):
        """
        Initialize UserView instance
        ---
        parameters:
            - name: is_api
              in: path
              type: boolean
              description: is api
        """
        self.json_data = request.get_json()
        self.is_api = is_api

    def get(self, user_id: int):
        """
        Get User information by ID
        ---
        tags:
        - 'User'
        parameters:
        - in: 'path'
          name: 'user_id'
          description: 'ID of the UserPost to retrieve'
          required: true
          schema:
            type: 'integer'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'UserPost'
              properties:
                id:
                  type: 'integer'
                  description: 'UserPost ID'
                name:
                  type: 'string'
                  description: 'Username'
                email:
                  type: 'string'
                  description: 'Email'
                group:
                  type: 'integer'
                  description: 'Group ID'
                enabled:
                  type: 'boolean'
                  description: 'UserPost account is active'
                last_login_date:
                  type: 'string'
                  format: 'date-time'
                  description: 'Last login date'
                last_login_ip:
                  type: 'string'
                  description: 'Last login IP'
          '404':
            description: 'UserPost not found'
            schema:
              id: 'NotFound'
              properties:
                message:
                  type: 'string'
                  description: 'Error message'
        """
        try:
            user = user_sql.get_user_id(user_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get user')

        try:
            roxywi_common.is_user_has_access_to_group(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find user'), 404

        return model_to_dict(user, exclude=[User_DB.password, User_DB.user_services])

    @validate(body=UserPost)
    def post(self, body: UserPost) -> Union[dict, tuple]:
        """
        Create UserPost
        ---
        tags:
          - User
        parameters:
          - name: body
            in: body
            schema:
              id: NewUser
              required:
                - email
                - password
                - role
                - username
                - enabled
                - user_group
              properties:
                email:
                  type: string
                  description: The email of the user
                password:
                  type: string
                  description: The password of the user
                role:
                  type: integer
                  description: The role of the user
                username:
                  type: string
                  description: The username of the user
                enabled:
                  type: integer
                  description: 'Enable status (1 for enabled)'
                group_id:
                  type: integer
                  description: The ID of the user's group
        responses:
          200:
            description: UserPost created
            schema:
              id: CreateUserResponse
              properties:
                status:
                  type: string
                  description: The status of the user creation
                id:
                  type: integer
                  description: The ID of the created user
        """
        if g.user_params['role'] > body.role:
            return roxywi_common.handle_json_exceptions('Wrong role', 'Cannot create user')
        try:
            user_id = roxywi_user.create_user(body.username, body.email, body.password, body.role, body.enabled, body.user_group)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create a new user')
        else:
            if self.is_api:
                return IdResponse(id=user_id), 201
            else:
                lang = roxywi_common.get_user_lang_for_flask()
                data = render_template(
                    'ajax/new_user.html', users=user_sql.select_users(user=body.username), groups=group_sql.select_groups(),
                    roles=sql.select_roles(), adding=1, lang=lang
                )
                return IdDataResponse(id=user_id, data=data), 201

    @validate(body=UserPut)
    def put(self, user_id: int, body: UserPut) -> Union[dict, tuple]:
        """
        Update User Information
        ---
        tags:
          - User
        description: Update the information of a user based on the provided user ID.
        parameters:
          - in: 'path'
            name: 'user_id'
            description: 'ID of the UserPost to retrieve'
            required: true
            schema:
              type: 'integer'
          - in: body
            name: body
            schema:
              id: UserUpdate
              required:
                - id
                - username
                - email
                - enabled
              properties:
                email:
                  type: string
                  description: The email of the user
                username:
                  type: string
                  description: The username of the user
                enabled:
                  type: integer
                  description: 'Enable status (1 for enabled)'
        responses:
          400:
            description: Invalid request
          201:
            description: UserPost information update successful
        """
        try:
            user = user_sql.get_user_id(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user'), 404
        try:
            user_sql.update_user_from_admin_area(body.username, body.email, user_id, body.enabled)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update user')
        roxywi_common.logging(body.username, 'has been updated user', roxywi=1, login=1)
        return BaseResponse(), 201

    @validate()
    def delete(self, user_id: int):
        """
        Delete a User
        ---
        tags:
          - User
        Description: Delete a user based on the provided user ID.
        parameters:
        - in: 'path'
          name: 'user_id'
          description: 'User ID to delete'
          required: true
          schema:
            type: 'integer'
        responses:
          204:
            description: UserPost deletion successful
          400:
            description: Invalid request
          404:
            description: UserPost not found
        """
        try:
            roxywi_common.is_user_has_access_to_group(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find user'), 404
        try:
            user = user_sql.get_user_id(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user'), 404

        if g.user_params['role'] > int(user.role):
            return roxywi_common.handle_json_exceptions('Wrong role', 'Cannot delete user'), 404

        try:
            roxywi_user.delete_user(user_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot delete the user')


class UserGroupView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(), check_group()]

    def __init__(self, is_api: bool = False):
        self.json_data = request.get_json()

    def get(self, group_id: int):
        """
        Fetch a specific User Group.
        ---
        tags:
          - User group
        parameters:
        - in: 'path'
          name: 'group_id'
          description: 'Group ID to list'
          required: true
          schema:
            type: 'integer'
        responses:
          200:
            description: A list of users in the group
            schema:
              type: array
              items:
                id: UserPost
                properties:
                  email:
                    type: string
                    description: The user's email
                    example: "admin@localhost1"
                  enabled:
                    type: integer
                    description: Indicates whether the user is enabled or not
                    example: 1
                  group:
                    type: integer
                    description: The ID of the group
                    example: 1
                  id:
                    type: integer
                    description: The ID of the user
                    example: 1
                  last_login_date:
                    type: string
                    format: date-time
                    description: The last login date of the user
                    example: "Thu, 27 Jun 2024 18:47:51 GMT"
                  last_login_ip:
                    type: string
                    description: The IP address from which the user last logged in
                    example: "10.0.0.148"
                  ldap:
                    type: integer
                    description: Indicates whether the user is an LDAP user or not
                    example: 0
                  role:
                    type: integer
                    description: The role of the user
                    example: 1
                  username:
                    type: string
                    description: The username of the user
                    example: "admin"
        """
        try:
            users = user_sql.get_users_in_group(group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get group')

        json_data = []
        for user in users:
            json_data.append(model_to_dict(user, exclude=[User_DB.password, User_DB.user_services]))

        return jsonify(json_data)

    @validate(body=AddUserToGroup)
    def post(self, body: AddUserToGroup):
        """
        Add or Update a User in a group
        ---
        tags:
          - User group
        parameters:
          - in: body
            name: body
            schema:
              id: AddUserGroup
              required:
                - group_id
                - user_id
                - role_id
              properties:
                group_id:
                  type: integer
                  description: The group ID
                user_id:
                  type: integer
                  description: The user ID
                role_id:
                  type: integer
                  description: The role ID
        responses:
          201:
            description: UserPost addition to group successful
        """
        try:
            _ = user_sql.get_user_id(body.user_id)
            groups = group_sql.select_groups(id=body.group_id)
            if len(groups) == 0:
                raise RoxywiResourceNotFound
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user or group'), 404
        try:
            user_sql.update_user_role(body.user_id, body.group_id, body.role_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot add user to group'), 500
        else:
            return BaseResponse().model_dump(mode='json'), 201

    def delete(self):
        """
        Remove a User from a group
        ---
        tags:
          - User group
        parameters:
          - in: body
            name: body
            schema:
              id: RemoveUserGroup
              required:
                - group_id
                - user_id
              properties:
                group_id:
                  type: integer
                  description: The group ID
                user_id:
                  type: integer
                  description: The user ID
        responses:
          204:
            description: UserPost removal from group successful
          400:
            description: Invalid request
          404:
            description: UserPost not found
        """
        try:
            group_id = int(self.json_data['group_id'])
            user_id = int(self.json_data['user_id'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get user data'), 400

        try:
            _ = user_sql.get_user_id(user_id)
            groups = group_sql.select_groups(group_id)
            if len(groups) == 0:
                raise RoxywiResourceNotFound
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user or group'), 404

        try:
            user_sql.delete_user_from_group(group_id, user_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete user')
