from flask import jsonify
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask_pydantic import validate
from playhouse.shortcuts import model_to_dict

import app.modules.db.history as history_sql
import app.modules.roxywi.common as roxywi_common
from app.middleware import get_user_params, check_group, page_for_admin
from app.modules.common.common_classes import SupportClass
from app.modules.db.db_model import RMONAlertsHistory
from app.modules.roxywi.class_models import HistoryQuery


class ChecksHistoryView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group(), page_for_admin(level=3)]

    @validate(query=HistoryQuery)
    def get(self, query: HistoryQuery):
        """
        Retrieve the checks history with optional filtering by group_id (available only for the superAdmin role) and optional recursive fetching.

        ---
        tags:
          - Check History
        parameters:
          - in: query
            name: group_id
            required: false
            type: integer
            description: Group ID (only for superAdmin role)
          - in: query
            name: recurse
            required: false
            type: boolean
            default: false
            description: Whether to fetch the data recursively
          - name: offset
            in: query
            type: integer
            description: 'Offset for pagination.'
            default: 1
          - name: limit
            in: query
            type: integer
            description: 'Limit for pagination.'
            default: 25
          - name: sort_by
            in: query
            description: 'Sort checks by check status. If add "-" to a value it will be sorted by ASC. Available values: `name`, `id`, `date`.'
            required: false
            type: 'string'
        responses:
          200:
            description: Successful response with checks history
            schema:
              type: object
              properties:
                result:
                  type: array
                  items:
                    type: object
                    properties:
                      date:
                        type: string
                        format: date-time
                        example: "Tue, 29 Oct 2024 19:47:20 GMT"
                      group_id:
                        type: integer
                        example: 1
                      id:
                        type: integer
                        example: 37
                      level:
                        type: string
                        example: "warning"
                      message:
                        type: string
                      name:
                        type: string
                        example: "'DNS check'"
                      port:
                        type: integer
                        example: 80
                      rmon_id:
                        type: integer
                        example: 2
                total:
                  type: integer
                  description: Total entries.
                  example: 175
          400:
            description: Request error
          401:
            description: Not authorized
          403:
            description: Access forbidden
          404:
            description: Resource not found
        """
        group_id = SupportClass.return_group_id(query)

        try:
            history = history_sql.alerts_history('RMON', group_id, query)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get history')
        total_history = history_sql.total_alerts_history('RMON', group_id)
        history_list = {'results': [], 'total': total_history}
        for h in history:
            history = model_to_dict(h, recurse=query.recurse, exclude={RMONAlertsHistory.service}, max_depth=1)
            history['name'] = history['name'].replace("'", "")
            history_list['results'].append(history)
        return jsonify(history_list)


class CheckHistoryView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group(), page_for_admin(level=3)]

    @validate(query=HistoryQuery)
    def get(self, check_id: int, query: HistoryQuery):
        """
        Retrieve the check history by check ID with optional filtering by group_id (available only for the superAdmin role) and optional recursive fetching.

        ---
        tags:
          - Check History
        parameters:
          - in: path
            name: check_id
            required: true
            type: integer
            description: ID of the check to retrieve
          - in: query
            name: group_id
            required: false
            type: integer
            description: Group ID (only for superAdmin role)
          - in: query
            name: recurse
            required: false
            type: boolean
            default: false
            description: Whether to fetch the data recursively
          - name: offset
            in: query
            type: integer
            description: 'Offset for pagination.'
            default: 1
          - name: limit
            in: query
            type: integer
            description: 'Limit for pagination.'
            default: 25
          - name: sort_by
            in: query
            description: 'Sort checks by check status. If add "-" to a value it will be sorted by ASC. Available values: `name`, `id`, `date`.'
            required: false
            type: 'string'
        responses:
          200:
            description: Successful response with checks history
            schema:
              type: object
              properties:
                result:
                  type: array
                  items:
                    type: object
                    properties:
                      date:
                        type: string
                        format: date-time
                        example: "Tue, 29 Oct 2024 19:47:20 GMT"
                      group_id:
                        type: integer
                        example: 1
                      id:
                        type: integer
                        example: 37
                      level:
                        type: string
                        example: "warning"
                      message:
                        type: string
                      name:
                        type: string
                        example: "'DNS check'"
                      port:
                        type: integer
                        example: 80
                      rmon_id:
                        type: integer
                        example: 2
                total:
                  type: integer
                  description: Total entries.
                  example: 175
          400:
            description: Request error
          401:
            description: Not authorized
          403:
            description: Access forbidden
          404:
            description: Resource not found
        """
        group_id = SupportClass.return_group_id(query)

        try:
            history = history_sql.rmon_multi_check_history(check_id, group_id, query)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get history')
        total_history = history_sql.total_rmon_multi_check_history(check_id, group_id)
        history_list = {'results': [], 'total': total_history}
        for h in history:
            history = model_to_dict(h, recurse=query.recurse, exclude={RMONAlertsHistory.service}, max_depth=1)
            history['name'] = history['name'].replace("'", "")
            history_list['results'].append(history)
        return jsonify(history_list)
