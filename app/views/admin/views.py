from typing import Optional

from flask.views import MethodView
from flask_pydantic import validate
from flask import jsonify
from playhouse.shortcuts import model_to_dict
from flask_jwt_extended import jwt_required

import app.modules.db.sql as sql
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.smon as smon_mod
from app.middleware import get_user_params, page_for_admin, check_group
from app.modules.roxywi.class_models import (
    BaseResponse, GroupQuery, SettingsRequest
)
from app.views.server.views import BaseServer


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
          description: The name of the settings section. Only 'main', 'rmon', 'rabbitmq', 'ldap', 'monitoring', 'logs' are allowed. If none get all settings.
          required: true
          type: string
          enum: ['main', 'rmon', 'rabbitmq', 'ldap', 'monitoring', 'logs']
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
                  desc:
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
            group_id = BaseServer.return_group_id(query)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, f'Cannot get Settings')

        settings = sql.get_setting('', group_id=group_id, section=section, all=1)

        return jsonify([model_to_dict(setting) for setting in settings])

    @validate(body=SettingsRequest, query=GroupQuery)
    def post(self, section: str, body: SettingsRequest, query: GroupQuery):
        val = body.value.replace('92', '/')
        try:
            group_id = BaseServer.return_group_id(query)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, f'Cannot get Settings')
        try:
            sql.update_setting(body.param, val, group_id)
        except Exception as e:
            roxywi_common.handle_json_exceptions(e, 'Cannot update settings')
        roxywi_common.logging('Roxy-WI server', f'The {body.param} setting has been changed to: {val}', roxywi=1, login=1)

        if body.param == 'master_port':
            try:
                smon_mod.change_smon_port(int(val))
            except Exception as e:
                return f'{e}'
        return BaseResponse().model_dump(mode='json'), 201
