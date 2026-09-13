from typing import Optional

from flask.views import MethodView
from flask_pydantic import validate
from flask import jsonify
from playhouse.shortcuts import model_to_dict
from flask_jwt_extended import jwt_required

import app.modules.db.sql as sql
import app.modules.roxywi.roxy as roxy
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.smon as smon_mod
from app.middleware import get_user_params, page_for_admin, check_group
from app.modules.roxywi.class_models import BaseResponse, GroupQuery, SettingsRequest
from app.modules.common.common_classes import SupportClass
from app.modules.common import agent_transport


class SettingsView(MethodView):
    methods = ['GET', 'POST']
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2), check_group()]

    @validate(query=GroupQuery)
    def get(self, section: Optional[str], query: GroupQuery):
        """
        Get Settings
        ---
        tags:
          - Settings
        summary: Get settings of the application.
        description: Returns either all settings or settings from the specified section.
        parameters:
        - name: section
          in: path
          description: The name of the settings section. Only 'main', 'rmon', 'ldap', 'monitoring', 'logs' are allowed. If none get all settings.
          required: true
          type: string
          enum: ['main', 'rmon', 'ldap', 'monitoring', 'logs']
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        produces:
          - application/json
        responses:
          200:
            description: OK
            schema:
              type: array
              items:
                type: object
                properties:
                  description:
                    type: string
                    description: The description of the setting.
                    example: "List of IP addresses or names to connect to the RMON masters. Specified separated by commas"
                  group:
                    type: integer
                    description: The group number of the setting.
                    example: 1
                  param:
                    type: string
                    description: The parameter name of the setting.
                    example: "master_ip"
                  section:
                    type: string
                    description: The section name of the setting.
                    example: "rmon"
                  value:
                    type: string
                    description: The value of the setting.
                    example: "10.0.0.75,10.0.0.76"
        """
        try:
            group_id = SupportClass.return_group_id(query)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get Settings')

        settings = sql.get_setting('', group_id=group_id,
                                   section='smon' if section == 'rmon' else section, all=section is None)

        return jsonify([model_to_dict(setting) for setting in settings])

    @validate(body=SettingsRequest, query=GroupQuery)
    def post(self, section: str, body: SettingsRequest, query: GroupQuery):
        """
        Update settings
        ---
        tags:
          - Settings
        summary: Create or update a setting.
        description: Can be used to create a new setting or update an existing one in the specified section.
        parameters:
        - name: section
          in: path
          description: The name of the settings section. Only 'main', 'rmon', 'ldap', 'monitoring', 'logs' are allowed.
          required: true
          type: string
          enum: ['main', 'rmon', 'ldap', 'monitoring', 'logs']
        - name: group_id
          in: query
          description: The parameter is used only for the superAdmin role.
          required: false
          type: integer
        - name: body
          in: body
          description: Updated settings values.
          required: true
          schema:
            type: object
            properties:
              param:
                type: string
                description: The parameter name of the setting.
              value:
                type: string
                description: The new value for the setting.
            example:
              param: "some_param"
              value: "some_value"
        produces:
          - application/json
        responses:
          201:
            description: OK
        """
        try:
            group_id = SupportClass.return_group_id(query)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get Settings')
        try:
            if body.param in agent_transport.DEFAULTS or section == 'agent':
                if section != 'agent':
                    raise ValueError('Use the agent connection settings section')
                body.value = agent_transport.validate_setting(body.param, body.value, group_id)
            sql.update_setting(body.param, body.value, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update settings'), 400
        if body.param in agent_transport.DEFAULTS:
            roxywi_common.logger(f'The {body.param} setting has been changed', login=1)
        else:
            roxywi_common.logger(f'The {body.param} setting has been changed to: {body.value}', login=1)

        if body.param == 'master_port':
            try:
                smon_mod.change_smon_port(int(body.value))
            except Exception as e:
                return f'{e}'
        if body.param == 'license':
            roxy.update_plan()
        return BaseResponse().model_dump(mode='json'), 201
