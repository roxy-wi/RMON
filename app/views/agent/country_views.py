from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify
from playhouse.shortcuts import model_to_dict
from flask_pydantic import validate

import app.modules.db.region as region_sql
import app.modules.db.country as country_sql
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
from app.middleware import get_user_params, check_group
from app.modules.roxywi.class_models import BaseResponse, IdResponse, GroupQuery, CountryRequest
from app.modules.common.common_classes import SupportClass


class CountryView(MethodView):
    method_decorators = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=GroupQuery)
    def get(self, country_id: int, query: GroupQuery):
        """
        Retrieve country information based on the provided country_id.
        ---
        tags:
         - Country
        parameters:
          - name: country_id
            in: path
            type: integer
            required: true
            description: The identifier of the region
          - in: 'query'
            name: 'group_id'
            description: 'ID of the group to list countries. For superAdmin only'
            required: false
            type: 'integer'
        responses:
          200:
            description: Successfully retrieved country information
            schema:
              type: object
              properties:
                country_id:
                  type: integer
                  nullable: true
                  description: The identifier of the country (can be null)
                description:
                  type: string
                  description: Description of the country
                enabled:
                  type: integer
                  description: Country enabled flag (1 - enabled, 0 - disabled)
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
            country = country_sql.get_country_with_group(country_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot find the country')

        return jsonify(model_to_dict(country))

    @validate(body=CountryRequest)
    def post(self, body: CountryRequest):
        """
        Create a new country with the provided information.
        ---
        tags:
        - Country
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
                  description: Description of the country
                  example: ""
                enabled:
                  type: integer
                  description: Country enabled flag (1 - enabled, 0 - disabled)
                  example: 1
                shared:
                  type: integer
                  description: Shared flag (1 - shared, 0 - not shared)
                  example: 0
                regions:
                  type: array
                  items:
                    type: string
                  description: List of regions associated with the country
                  example: []
        responses:
          201:
            description: Successfully created country
        """
        roxywi_auth.page_for_admin(level=2)
        group_id = SupportClass.return_group_id(body)
        body.group_id = group_id
        try:
            last_id = country_sql.create_country(body)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create the country')
        try:
            if body.regions:
                for region in body.regions:
                    region_sql.add_region_to_country(region, last_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot add regions to the new country')

        return IdResponse(id=last_id).model_dump(mode='json'), 201

    @validate(body=CountryRequest)
    def put(self, country_id: int, body: CountryRequest):
        """
        Update an existing country with the provided information.
        ---
        tags:
        - Country
        parameters:
          - name: country_id
            in: path
            type: integer
            required: true
            description: The identifier of the country to be updated
          - name: body
            in: body
            required: true
            description: JSON object containing updated region details
            schema:
              type: object
              properties:
                name:
                  type: string
                  description: Name of the country
                  example: "Italy"
                description:
                  type: string
                  description: Description of the country
                  example: ""
                enabled:
                  type: integer
                  description: Region enabled flag (1 - enabled, 0 - disabled)
                  example: 1
                shared:
                  type: integer
                  description: Shared flag (1 - shared, 0 - not shared)
                  example: 0
                regions:
                  type: array
                  items:
                    type: string
                  description: List of regions associated with the country
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
            country_sql.update_country(body, country_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot create the country')

        try:
            regions = region_sql.get_regions_by_country(country_id)
            for region in regions:
                region_sql.add_region_to_country(region.id, None)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot update regions')

        try:
            if body.regions:
                for region in body.regions:
                    region_sql.add_region_to_country(region, country_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot add agents to the country')

        return BaseResponse().model_dump(mode='json'), 201

    @staticmethod
    @validate(query=GroupQuery)
    def delete(country_id: int, query: GroupQuery):
        """
        Delete a country based on the provided country_id.
        ---
        tags:
        - Country
        parameters:
          - name: country_id
            in: path
            type: integer
            required: true
            description: The identifier of the country to be deleted
          - in: 'query'
            name: 'group_id'
            description: 'ID of the group to list countries. For superAdmin only'
            required: false
            type: 'integer'
        responses:
          204:
            description: Successfully deleted the country
          404:
            description: Region not found
        """
        roxywi_auth.page_for_admin(level=2)
        group_id = SupportClass.return_group_id(query)
        try:
            country_sql.get_country_with_group(country_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot find the country')

        try:
            country_sql.delete_country(country_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot delete the country')


class CountryListView(MethodView):
    method_decorators = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Retrieve a list of countries.
        ---
        tags:
        - Country
        parameters:
          - in: 'query'
            name: 'group_id'
            description: 'ID of the group to list countries. For superAdmin only'
            required: false
            type: 'integer'
        responses:
          200:
            description: Successfully retrieved list of countries
            schema:
              type: array
              items:
                type: object
                properties:
                  description:
                    type: string
                    description: Description of the country
                  enabled:
                    type: integer
                    description: Country enabled flag (1 - enabled, 0 - disabled)
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
            examples:
              application/json: [
                {
                  "description": "",
                  "enabled": 1,
                  "group_id": 1,
                  "id": 1,
                  "name": "Malta",
                  "shared": 0
                },
                {
                  "description": "",
                  "enabled": 1,
                  "group_id": 1,
                  "id": 2,
                  "name": "Spain",
                  "shared": 0
                }
              ]
        """
        group_id = SupportClass.return_group_id(query)
        try:
            countries = country_sql.select_countries_by_group(group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get countries')

        return jsonify([model_to_dict(country) for country in countries])
