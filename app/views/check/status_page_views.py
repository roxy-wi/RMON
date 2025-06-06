from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify
from flask_pydantic import validate
from playhouse.shortcuts import model_to_dict

import app.modules.db.smon as smon_sql
import app.modules.tools.smon as smon_mod
import app.modules.roxywi.common as roxywi_common
from app.middleware import get_user_params, check_group
from app.modules.common.common_classes import SupportClass
from app.modules.db.db_model import SmonStatusPageCheck, SmonStatusPage
from app.modules.roxywi.class_models import GroupQuery, BaseResponse, StatusPageRequest, ErrorResponse, IdResponse, \
    EscapedString


class StatusPageView(MethodView):
    methods = ['GET', 'POST', 'PUT', 'DELETE']
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=GroupQuery)
    def get(self, page_id: int, query: GroupQuery):
        """
        Get Status Page
        ---
        tags:
          - Status Page
        summary: Retrieve the status page details.
        description: Fetches the details of a specific status page by `page_id`. The `group_id` query parameter can be used only by users with the superAdmin role.
        parameters:
        - name: page_id
          in: path
          description: The ID of the status page to retrieve.
          required: true
          type: integer
        - name: group_id
          in: query
          description: The group ID for the superAdmin role.
          required: false
          type: integer
        - name: recurse
          in: query
          type: boolean
          description: Whether to recursively include associated checks.
          required: false
          default: false
        - name: max_depth
          in: query
          type: integer
          description: The maximum depth of recursion to apply.
          default: 1
          required: false
        responses:
          200:
            description: Successful response
            schema:
              type: object
              properties:
                checks:
                  type: array
                  items:
                    type: object
                    properties:
                      check_id:
                        type: integer
                custom_style:
                  type: string
                  example: ""
                description:
                  type: string
                  example: "Some checks for the status page"
                group_id:
                  type: integer
                  example: 1
                id:
                  type: integer
                  example: 1
                name:
                  type: string
                  example: "Status-page"
                slug:
                  type: string
                  example: "status-page"
        """
        try:
            group_id = SupportClass.return_group_id(query)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get Status page group')

        try:
            page = smon_sql.select_status_page_with_group(page_id, group_id)
            page = model_to_dict(page)
            page['description'] = page['description'].replace("'", "")
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get Status page')

        try:
            checks = smon_sql.select_status_page_checks(page_id)
            page['checks'] = []
            for check in checks:
                page['checks'].append(model_to_dict(check, recurse=query.recurse, max_depth=query.max_depth, exclude=[SmonStatusPageCheck.page_id]))
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get Status page checks')

        return jsonify(page)

    @validate(body=StatusPageRequest)
    def post(self, body: StatusPageRequest):
        """
        Create a Status Page
        ---
        tags:
          - Status Page
        summary: Create a new Status page.
        description: Create a new Status page`.
        parameters:
        - name: body
          in: body
          description: The created status page details.
          required: true
          schema:
            type: object
            properties:
              name:
                type: string
                example: "test1"
                description: The name of the status page.
              slug:
                type: string
                example: "test1"
                description: The slug of the status page.
              description:
                type: string
                example: "admin1"
                description: The description of the status page.
              custom_style:
                type: string
                example: ""
                description: Custom CSS style for the status page.
              checks:
                type: array
                items:
                  type: integer
                example: []
                description: List of checks associated with the status page.
              group_id:
                type: integer
                example: 2
                description: The group ID associated with the status page. Parameter can be used only by users with the superAdmin role.
        responses:
          201:
            description: OK
        """
        try:
            group_id = SupportClass.return_group_id(body)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Wrong group')

        if not len(body.checks):
            return ErrorResponse(error='There is must be at least one check'), 500

        try:
            page_id = smon_mod.create_status_page(body.name, body.slug, body.description, body.checks, body.custom_style, group_id)
            return IdResponse(id=page_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create Status page')

    @validate(body=StatusPageRequest)
    def put(self, page_id: int, body: StatusPageRequest):
        """
        Update Status Page
        ---
        tags:
          - Status Page
        summary: Update the status page.
        description: Updates a specific status page by `page_id`.
        parameters:
        - name: page_id
          in: path
          description: The ID of the status page to update.
          required: true
          type: integer
        - name: body
          in: body
          description: The updated status page details.
          required: true
          schema:
            type: object
            properties:
              name:
                type: string
                example: "test1"
                description: The name of the status page.
              slug:
                type: string
                example: "test1"
                description: The slug of the status page.
              description:
                type: string
                example: "admin1"
                description: The description of the status page.
              custom_style:
                type: string
                example: ""
                description: Custom CSS style for the status page.
              checks:
                type: array
                items:
                  type: integer
                example: []
                description: List of checks associated with the status page.
              group_id:
                type: integer
                example: 2
                description: The group ID associated with the status page. Parameter can be used only by users with the superAdmin role.
        responses:
          201:
            description: OK
        """
        try:
            group_id = SupportClass.return_group_id(body)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Wrong group')

        try:
            _ = smon_sql.select_status_page_with_group(page_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot find Status page')

        if not len(body.checks):
            return ErrorResponse(error='There is must be at least one check'), 500

        try:
            smon_mod.edit_status_page(page_id, body.name, body.slug, body.description, body.checks, body.custom_style)
            return BaseResponse().model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot edit Status page')

    @validate(query=GroupQuery)
    def delete(self, page_id: int, query: GroupQuery):
        """
        Delete Status Page
        ---
        tags:
          - Status Page
        summary: Delete the status page.
        description: Deletes a specific status page by `page_id`. The `group_id` query parameter can be used only by users with the superAdmin role.
        parameters:
        - name: page_id
          in: path
          description: The ID of the status page to delete.
          required: true
          type: integer
        - name: group_id
          in: query
          description: The group ID for the superAdmin role.
          required: false
          type: integer
        responses:
          204:
            description: OK
          404:
            description: Not Found
        """
        try:
            group_id = SupportClass.return_group_id(query)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get Status page group')

        try:
            _ = smon_sql.select_status_page_with_group(page_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot find Status page')

        try:
            smon_sql.delete_status_page(page_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot delete Status page')


class StatusPages(MethodView):
    methods = ['GET', 'POST', 'PUT', 'DELETE']
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Get Status Pages
        ---
        tags:
          - Status Pages
        summary: Retrieve the status pages details.
        description: Fetches list of status pages for a user group. The `group_id` query parameter can be used only by users with the superAdmin role.
        parameters:
        - name: group_id
          in: query
          description: The group ID for the superAdmin role.
          required: false
          type: integer
        responses:
          200:
            description: Successful response
            schema:
              type: array
              items:
                type: object
                properties:
                  description:
                    type: string
                    example: "Some checks for the status page"
                  group_id:
                    type: integer
                    example: 1
                  id:
                    type: integer
                    example: 1
                  name:
                    type: string
                    example: "Status-page"
                  slug:
                    type: string
                    example: "status-page"
        """
        pages_list = []
        try:
            group_id = SupportClass.return_group_id(query)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get Status page group')

        try:
            pages = smon_sql.select_status_pages(group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get Status page')

        for page in pages:
            page = model_to_dict(page, exclude={SmonStatusPage.custom_style})
            page['description'] = page['description'].replace("'", "")
            pages_list.append(page)

        return jsonify(pages_list)


class StatusPageSlug(MethodView):
    methods = ['GET']

    def get(self, slug: EscapedString):
        """
        Get Status Page by slug
        ---
        tags:
          - Status Page
        summary: Retrieve the status page details.
        description: Fetches the details of a specific status page by `slug`.
        parameters:
        - name: slug
          in: path
          description: The ID of the status page to retrieve.
          required: true
          type: string
        responses:
          200:
            description: Successful response
            schema:
              type: object
              properties:
                checks:
                  type: array
                  items:
                    type: object
                    properties:
                      check_id:
                        type: integer
                custom_style:
                  type: string
                  example: ""
                description:
                  type: string
                  example: "Some checks for the status page"
                group_id:
                  type: integer
                  example: 1
                id:
                  type: integer
                  example: 1
                name:
                  type: string
                  example: "Status-page"
                slug:
                  type: string
                  example: "status-page"
                check_group:
                  type: string
        """
        try:
            page = smon_sql.get_status_page(slug)
            page = model_to_dict(page)
            page['description'] = page['description'].replace("'", "")
            page_id = page['id']
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get Status page')

        try:
            checks = smon_sql.select_status_page_checks(page_id)
            page['checks'] = []
            group_name = ''
            for check in checks:
                group_name = ''
                check_data = smon_sql.select_one_smon_by_multi_check(check.multi_check_id)
                for c_d in check_data:
                    if c_d.multi_check_id.check_group_id:
                        group_name = smon_sql.get_smon_group_by_id(c_d.multi_check_id.check_group_id).name
                        group_name = group_name.replace("'", "")
                    page['checks'].append(model_to_dict(c_d, recurse=False))
            for check in page['checks']:
                check.update(smon_sql.get_uptime_and_status(check['multi_check_id']))
                check.update({'check_group': group_name})
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get Status page checks')

        return jsonify(page)
