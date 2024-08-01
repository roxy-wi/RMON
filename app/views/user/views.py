from typing import Union

from flask.views import MethodView
from flask_pydantic import validate
from flask_jwt_extended import jwt_required, set_access_cookies
from flask import render_template, jsonify, g
from playhouse.shortcuts import model_to_dict

import app.modules.db.sql as sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.user as roxywi_user
import app.modules.roxywi.common as roxywi_common
from app.modules.db.db_model import User as User_DB
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.roxywi.class_models import (
    UserPost, UserPut, IdResponse, IdDataResponse, BaseResponse, AddUserToGroup, GroupQuery
)
from app.middleware import get_user_params, page_for_admin, check_group
from app.views.server.views import BaseServer


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
          description: 'ID of the User to retrieve'
          required: true
          type: 'integer'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              type: 'object'
              id: 'User'
              properties:
                user_group_id:
                  type: 'object'
                  properties:
                    description:
                      type: 'string'
                      description: 'Group description'
                    group_id:
                      type: 'integer'
                      description: 'Group ID'
                    name:
                      type: 'string'
                      description: 'Group name'
                user_id:
                  type: 'object'
                  properties:
                    email:
                      type: 'string'
                      description: 'User email'
                    enabled:
                      type: 'integer'
                      description: 'User activation status'
                    last_login_date:
                      type: 'string'
                      format: 'date-time'
                      description: 'User last login date'
                    last_login_ip:
                      type: 'string'
                      description: 'User last login IP'
                    ldap_user:
                      type: 'integer'
                      description: 'Is User a LDAP user'
                    role:
                      type: 'string'
                      description: 'User role'
                    user_id:
                      type: 'integer'
                      description: 'User ID'
                    username:
                      type: 'string'
                      description: 'Username'
                user_role_id:
                  type: 'integer'
                  description: 'User role ID'
          '404':
            description: 'User not found'
            schema:
              id: 'NotFound'
              properties:
                message:
                  type: 'string'
                  description: 'Error message'
        """
        users_list = []
        try:
            users = user_sql.select_user_groups_with_names(user_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get user')

        try:
            roxywi_common.is_user_has_access_to_group(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find user'), 404
        for user in users:
            users_list.append(model_to_dict(user, exclude={User_DB.group_id, User_DB.password, User_DB.user_services}))
        return jsonify(users_list)

    @validate(body=UserPost)
    def post(self, body: UserPost) -> Union[dict, tuple]:
        """
        Create a new user
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
            description: user created
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
            description: 'ID of the User to retrieve'
            required: true
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
            description: User information update successful
        """
        try:
            _ = user_sql.get_user_id(user_id)
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
          type: 'integer'
        responses:
          204:
            description: User deletion successful
          400:
            description: Invalid request
          404:
            description: User not found
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
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot delete the user')


class UserGroupView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=4), check_group()]

    def get(self, user_id: int):
        """
        Fetch a specific User Group.
        ---
        tags:
          - User group
        parameters:
        - in: 'path'
          name: 'user_id'
          description: 'User ID to get'
          required: true
          type: 'integer'
        responses:
          200:
            description: A list of user's groups
            schema:
              type: array
              items:
                id: UserGet
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
            users = user_sql.select_user_groups_with_names(user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get group')

        json_data = []
        for user in users:
            json_data.append(model_to_dict(user, exclude=[User_DB.password, User_DB.user_services]))

        return jsonify(json_data)

    @validate(body=AddUserToGroup)
    def post(self, user_id: int, group_id: int, body: AddUserToGroup):
        """
        Add a User to a specific Group
        ---
        tags:
        - 'User group'
        parameters:
        - in: 'path'
          name: 'user_id'
          description: 'ID of the User to be added'
          required: true
          type: 'integer'
        - in: 'path'
          name: 'group_id'
          description: 'ID of the Group which will have a new user'
          required: true
          type: 'integer'
        - in: body
          name: role_id
          required: true
          schema:
            properties:
              role_id:
                type: integer
                description: A role inside the group
        responses:
          '201':
            description: 'User successfully added to the group'
          '404':
            description: 'User or Group not found'
        """
        page_for_admin(level=2)
        try:
            self._check_is_user_and_group(user_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user or group'), 404
        try:
            user_sql.update_user_role(user_id, group_id, body.role_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot add user to group'), 500
        else:
            return BaseResponse().model_dump(mode='json'), 201

    @validate(body=AddUserToGroup)
    def put(self, user_id: int, group_id: int, body: AddUserToGroup):
        """
        Update a User to a specific Group
        ---
        tags:
        - 'User group'
        parameters:
        - in: 'path'
          name: 'user_id'
          description: 'ID of the User to be added'
          required: true
          type: 'integer'
        - in: 'path'
          name: 'group_id'
          description: 'ID of the Group where updating the user'
          required: true
          type: 'integer'
        - in: body
          name: role_id
          required: true
          schema:
            properties:
              role_id:
                type: integer
                description: A role inside the group
        responses:
          '201':
            description: 'User successfully added to the group'
          '404':
            description: 'User or Group not found'
        """
        page_for_admin(level=2)
        try:
            self._check_is_user_and_group(user_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user or group'), 404

        try:
            user_sql.delete_user_from_group(group_id, user_id)
            user_sql.update_user_role(user_id, group_id, body.role_id)
            return BaseResponse().model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete user')

    def patch(self, user_id: int, group_id: int):
        """
        Assign a User to a specific Group
        ---
        tags:
          - 'User group'
        parameters:
          - in: 'path'
            name: 'user_id'
            description: 'ID of the User to be assigned to the group'
            required: true
            type: 'integer'
          - in: 'path'
            name: 'group_id'
            description: 'ID of the Group which the user will be assigned to'
            required: true
            type: 'integer'
        responses:
          201:
            description: 'User successfully assigned to the group'
          404:
            description: 'User or Group not found'
            schema:
              id: 'NotFound'
              properties:
                error:
                  type: 'string'
                  description: 'Error message'
        """
        try:
            self._check_is_user_and_group(user_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user or group'), 404

        user_param = {"user": user_id, "group": group_id}
        access_token = roxywi_auth.create_jwt_token(user_param)
        response = jsonify({'status': 'Ok'})
        set_access_cookies(response, access_token)
        try:
            user_sql.update_user_current_groups(group_id, user_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update user or group'), 500
        return response

    def delete(self, user_id: int, group_id: int):
        """
        Delete a User from a specific Group
        ---
        tags:
        - 'User group'
        parameters:
        - in: 'path'
          name: 'user_id'
          description: 'ID of the User to be deleted'
          required: true
          type: 'integer'
        - in: 'path'
          name: 'group_id'
          description: 'ID of the Group from which user will be deleted'
          required: true
          type: 'integer'
        responses:
          '204':
            description: 'User successfully deleted'
          '404':
            description: 'User or Group not found'
        """
        page_for_admin(level=2)
        try:
            self._check_is_user_and_group(user_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get user or group'), 404

        try:
            user_sql.delete_user_from_group(group_id, user_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete user')

    @staticmethod
    def _check_is_user_and_group(user_id: int, group_id: int):
        try:
            _ = user_sql.get_user_id(user_id)
            groups = group_sql.get_group_name_by_id(group_id)
            if len(groups) == 0:
                raise RoxywiResourceNotFound
        except Exception as e:
            raise e


class UsersView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(), check_group()]

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Get users information by Group ID.
        ---
        tags:
        - 'User'
        parameters:
        - in: 'query'
          name: 'group_id'
          description: 'GroupQuery to filter servers. Only for superAdmin role'
          required: false
          type: 'integer'
        responses:
          '200':
            description: 'Successful operation'
            schema:
              type: 'array'
              items:
                type: 'object'
                properties:
                  id:
                    type: 'integer'
                    description: 'Unique user ID'
                  name:
                    type: 'string'
                    description: 'Username'
                  email:
                    type: 'string'
                    description: 'User email address'
                  group:
                    type: 'integer'
                    description: 'Group ID of the user'
                  enabled:
                    type: 'boolean'
                    description: 'User account is active'
                  ldap:
                    type: 'boolean'
                    description: 'User is a LDAP user'
                  last_login_date:
                    type: 'string'
                    format: 'date-time'
                    description: 'Last login date'
                  last_login_ip:
                    type: 'string'
                    description: 'Last login IP'
          '404':
            description: 'Users not found'
            schema:
              id: 'NotFound'
              properties:
                message:
                  type: 'string'
                  description: 'Error message'
        """
        group_id = BaseServer.return_group_id(query)
        try:
            users = user_sql.get_users_in_group(group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get group')

        json_data = []
        for user in users:
            json_data.append(model_to_dict(user, exclude=[User_DB.password, User_DB.user_services]))
        return jsonify(json_data)


class UserRoles(MethodView):
    methods = ['GET']
    decorators = [jwt_required(), get_user_params(), page_for_admin()]

    def get(self):
        """
        User Roles
        ---
        tags:
          - User Roles
        summary: Get All User Role Information
        description: This method is used to retrieve all available user roles along with their descriptions and corresponding role_ids.
        produces:
          - application/json
        responses:
          200:
            description: User Roles Returned
            schema:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                    description: The name of the user role.
                    example: "superAdmin"
                  role_id:
                    type: integer
                    description: The ID of the user role.
                    example: 1
                  description:
                    type: string
                    description: The description of the user role.
                    example: "Has the highest level of administrative..."
        """
        try:
            roles = sql.select_roles()
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get roles')
        roles_list = []
        for role in roles:
            roles_list.append(model_to_dict(role))
        return jsonify(roles_list)
