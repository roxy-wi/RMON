from flask import jsonify
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask_pydantic import validate
from playhouse.shortcuts import model_to_dict

import app.modules.db.smon as smon_sql
import app.modules.roxywi.common as roxywi_common
from app.middleware import get_user_params, check_group, page_for_admin
from app.modules.common.common_classes import SupportClass
from app.modules.roxywi.class_models import CheckGroup, GroupQuery, IdResponse, BaseResponse


class CheckGroupView(MethodView):
    methods = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), check_group(), page_for_admin(level=3)]

    @validate(query=GroupQuery)
    def get(self, check_group_id: int, query: GroupQuery):
        """
        Retrieve details of a check group by its ID. The `group_id` query parameter is only available for the superAdmin role.

        ---
        tags:
          - Check Group
        parameters:
          - in: path
            name: check_group_id
            required: true
            type: integer
            description: ID of the check group to retrieve
          - in: query
            name: group_id
            required: false
            type: integer
            description: Group ID (only for superAdmin role)
        responses:
          200:
            description: A JSON object containing the group details
            schema:
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                name:
                  type: string
                  example: "smtp servers"
                group_id:
                  type: integer
                  example: 1
          400:
            description: Bad Request
          401:
            description: Unauthorized
          403:
            description: Forbidden
          404:
            description: Not Found
        """
        group_id = SupportClass.return_group_id(query)

        try:
            group = smon_sql.get_smon_group_by_id_with_group(check_group_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get group')
        group_list = model_to_dict(group)
        group_list['name'] = group_list['name'].replace("'", "")
        return jsonify(group_list)

    @validate(body=CheckGroup)
    def post(self, body: CheckGroup):
        """
        Create a new check group. The `group_id` is only available for users with the superAdmin role.

        ---
        tags:
          - Check Group
        parameters:
        - in: 'body'
          name: 'body'
          description: 'TCP Check Details'
          required: true
          schema:
            id: 'CheckGroupRequest'
            required:
              - name
            properties:
              name:
                type: string
                example: "smtp server"
              group_id:
                type: integer
                example: 2
                description: User group ID (only for superAdmin role)
        responses:
          201:
            description: Check group successfully created
            schema:
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                name:
                  type: string
                  example: "smtp server"
                group_id:
                  type: integer
                  example: 2
          400:
            description: Bad Request
          401:
            description: Unauthorized
          403:
            description: Forbidden
        """
        group_id = SupportClass.return_group_id(body)
        try:
            last_id = smon_sql.add_smon_group(group_id, body.name)
            return IdResponse(id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create group')

    @validate(body=CheckGroup)
    def put(self, check_group_id: int, body: CheckGroup):
        """
        Update a check group. The `group_id` is only available for users with the superAdmin role.

        ---
        tags:
          - Check Group
        parameters:
        - in: path
          name: check_group_id
          required: true
          type: integer
          description: ID of the check group to retrieve
        - in: query
          name: group_id
          required: false
          type: integer
          description: Group ID (only for superAdmin role)
        - in: 'body'
          name: 'body'
          description: 'TCP Check Details'
          required: true
          schema:
            id: 'CheckGroupRequest'
            required:
              - name
            properties:
              name:
                type: string
                example: "smtp server"
              group_id:
                type: integer
                example: 2
                description: User group ID (only for superAdmin role)
        responses:
          201:
            description: Check group successfully created
            schema:
              type: object
              properties:
                id:
                  type: integer
                  example: 1
                name:
                  type: string
                  example: "smtp server"
                group_id:
                  type: integer
                  example: 2
          400:
            description: Bad Request
          401:
            description: Unauthorized
          403:
            description: Forbidden
        """
        group_id = SupportClass.return_group_id(body)
        try:
            smon_sql.update_smon_group(check_group_id, body.name, group_id)
            return BaseResponse().model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update group')

    @validate(query=GroupQuery)
    def delete(self, check_group_id: int, query: GroupQuery):
        """
        Delete a check group by its ID. The `group_id` query parameter is only available for the superAdmin role.

        ---
        tags:
          - Check Group
        parameters:
          - in: path
            name: check_group_id
            required: true
            type: integer
            description: ID of the check group to retrieve
          - in: query
            name: group_id
            required: false
            type: integer
            description: Group ID (only for superAdmin role)
        responses:
          204:
            description: Group deleted
          400:
            description: Bad Request
          401:
            description: Unauthorized
          403:
            description: Forbidden
          404:
            description: Not Found
        """
        group_id = SupportClass.return_group_id(query)
        try:
            smon_sql.delete_smon_group(check_group_id, group_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete group')


class CheckGroupsView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group(), page_for_admin(level=3)]

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Retrieve details of check groups. The `group_id` query parameter is only available for the superAdmin role.

        ---
        tags:
          - Check Group
        parameters:
          - in: query
            name: group_id
            required: false
            type: integer
            description: Group ID (only for superAdmin role)
        responses:
          200:
            description: A JSON array containing the group details
            schema:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 1
                  name:
                    type: string
                    example: "smtp server"
                  group_id:
                    type: integer
                    example: 1
          400:
            description: Bad Request
          401:
            description: Unauthorized
          403:
            description: Forbidden
          404:
            description: Not Found
        """
        group_id = SupportClass.return_group_id(query)
        try:
            groups_list: list = []
            groups = smon_sql.select_smon_groups(group_id)
            for g in groups:
                group = model_to_dict(g)
                group['name'] = g.name.replace("'", "")
                groups_list.append(group)
            return jsonify(groups_list)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get groups')
