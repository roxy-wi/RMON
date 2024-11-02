from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify
from playhouse.shortcuts import model_to_dict
from flask_pydantic import validate

import app.modules.db.smon as smon_sql
import app.modules.db.region as region_sql
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
from app.middleware import get_user_params, check_group
from app.modules.roxywi.class_models import BaseResponse, IdResponse, GroupQuery, RegionRequest
from app.modules.common.common_classes import SupportClass


class RegionView(MethodView):
    method_decorators = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=GroupQuery)
    def get(self, region_id: int, query: GroupQuery):
        """
        Retrieve region information based on the provided region_id.
        ---
        tags:
         - Region
        parameters:
          - name: region_id
            in: path
            type: integer
            required: true
            description: The identifier of the region
          - name: group_id
            in: query
            description: This parameter is used only for the superAdmin role.
            required: false
            type: integer
        responses:
          200:
            description: Successfully retrieved country information
            schema:
              type: object
              properties:
                country_id:
                  type: integer
                  description: The identifier of the country (can be null)
                description:
                  type: string
                  description: Description of the region
                enabled:
                  type: integer
                  description: Region enabled flag (1 - enabled, 0 - disabled)
                group_id:
                  type: integer
                  description: The identifier of the group
                id:
                  type: integer
                  description: The identifier of the country in the system
                name:
                  type: string
                  description: Name of the country
                shared:
                  type: integer
                  description: Shared flag (1 - shared, 0 - not shared)
        """
        group_id = SupportClass.return_group_id(query)
        try:
            region = region_sql.get_region_with_group(region_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot find the region')

        return jsonify(model_to_dict(region, recurse=False))

    @validate(body=RegionRequest)
    def post(self, body: RegionRequest):
        """
        Create a new region with the provided information.
        ---
        tags:
        - Region
        parameters:
          - name: body
            in: body
            required: true
            description: JSON object containing country details
            schema:
              type: object
              properties:
                name:
                  type: string
                  description: Name of the country
                  example: "test"
                description:
                  type: string
                  description: Description of the region
                  example: ""
                enabled:
                  type: integer
                  description: Region enabled flag (1 - enabled, 0 - disabled)
                  example: 1
                shared:
                  type: integer
                  description: Shared flag (1 - shared, 0 - not shared)
                  example: 0
                agents:
                  type: array
                  items:
                    type: string
                  description: List of agents associated with the region
                  example: []
        responses:
          201:
            description: Successfully created country
        """
        roxywi_auth.page_for_admin(level=2)
        group_id = SupportClass.return_group_id(body)
        body.group_id = group_id
        try:
            last_id = region_sql.create_region(body)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create the region')
        try:
            if body.agents:
                for agent in body.agents:
                    smon_sql.update_agent(agent, region_id=last_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot add agents to the new region')

        return IdResponse(id=last_id).model_dump(mode='json'), 201

    @validate(body=RegionRequest)
    def put(self, region_id: int, body: RegionRequest):
        """
        Update an existing region with the provided information.
        ---
        tags:
        - Region
        parameters:
          - name: region_id
            in: path
            type: integer
            required: true
            description: The identifier of the region to be updated
          - name: body
            in: body
            required: true
            description: JSON object containing updated region details
            schema:
              type: object
              properties:
                name:
                  type: string
                  description: Name of the region
                  example: "DT"
                description:
                  type: string
                  description: Description of the region
                  example: ""
                enabled:
                  type: integer
                  description: Region enabled flag (1 - enabled, 0 - disabled)
                  example: 1
                shared:
                  type: integer
                  description: Shared flag (1 - shared, 0 - not shared)
                  example: 0
                agents:
                  type: array
                  items:
                    type: string
                  description: List of agents associated with the region
                  example:
                    - "1"
                    - "2"
        responses:
          200:
            description: Successfully updated region
        """
        roxywi_auth.page_for_admin(level=2)
        group_id = SupportClass.return_group_id(body)
        body.group_id = group_id
        try:
            region_sql.update_region(body, region_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create the region')

        try:
            agents = smon_sql.get_agents_by_region(region_id)
            for agent in agents:
                smon_sql.update_agent(agent, region_id=None)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot update agents')

        try:
            if body.agents:
                for agent in body.agents:
                    smon_sql.update_agent(agent, region_id=region_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot add agents to the region')

        return BaseResponse().model_dump(mode='json'), 201

    @staticmethod
    @validate(query=GroupQuery)
    def delete(region_id: int, query: GroupQuery):
        """
        Delete a region based on the provided region_id.
        ---
        tags:
        - Region
        parameters:
          - name: region_id
            in: path
            type: integer
            required: true
            description: The identifier of the region to be deleted
        responses:
          204:
            description: Successfully deleted the region
          404:
            description: Region not found
        """
        roxywi_auth.page_for_admin(level=2)
        group_id = SupportClass.return_group_id(query)
        try:
            region_sql.get_region_with_group(region_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot find the region')

        try:
            region_sql.delete_region(region_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot delete the region')


class RegionListView(MethodView):
    method_decorators = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Retrieve a list of regions.
        ---
        tags:
        - Region
        responses:
          200:
            description: Successfully retrieved list of regions
            schema:
              type: array
              items:
                type: object
                properties:
                  country_id:
                    type: integer
                    description: The identifier of the country (can be null)
                  description:
                    type: string
                    description: Description of the region
                  enabled:
                    type: integer
                    description: Region enabled flag (1 - enabled, 0 - disabled)
                  group_id:
                    type: integer
                    description: The identifier of the group
                  id:
                    type: integer
                    description: The identifier of the region in the system
                  name:
                    type: string
                    description: Name of the region
                  shared:
                    type: integer
                    description: Shared flag (1 - shared, 0 - not shared)
            examples:
              application/json: [
                {
                  "country_id": null,
                  "description": "",
                  "enabled": 1,
                  "group_id": 1,
                  "id": 1,
                  "name": "DT",
                  "shared": 0
                },
                {
                  "country_id": null,
                  "description": "",
                  "enabled": 1,
                  "group_id": 1,
                  "id": 2,
                  "name": "test",
                  "shared": 0
                }
              ]
        """
        group_id = SupportClass.return_group_id(query)
        try:
            regions = region_sql.select_regions_by_group(group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get regions')

        return jsonify([model_to_dict(region, recurse=False) for region in regions])
