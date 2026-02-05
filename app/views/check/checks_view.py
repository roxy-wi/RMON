from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify
from flask_pydantic import validate
from playhouse.shortcuts import model_to_dict

import app.modules.db.smon as smon_sql
import app.modules.tools.smon as smon_mod
from app.modules.common.common_classes import SupportClass
from app.middleware import get_user_params, check_group
from app.modules.roxywi.class_models import GroupQuery, CheckFiltersQuery
from app.modules.db.db_model import SMON


def _return_checks(checks: SMON, check_type_id: int = None) -> list:
    entities = []
    check_list = []

    for m in checks:
        check_json = {'checks': []}
        place = m.multi_check_id.entity_type
        check_id = m.id
        name = m.multi_check_id.name.replace("'", "")
        description = m.multi_check_id.description.replace("'", "")
        if m.multi_check_id.check_group_id:
            group_name = smon_sql.get_smon_group_by_id(m.multi_check_id.check_group_id).name
            group_name = group_name.replace("'", "")
        else:
            group_name = None
        check_json['check_group'] = group_name
        if m.country_id:
            entities.append(m.country_id.id)
        elif m.region_id:
            entities.append(m.region_id.id)
        elif m.agent_id:
            entities.append(m.agent_id.id)
        checks = smon_sql.select_one_smon(check_id, check_type_id=check_type_id)
        i = 0
        for check in checks:
            check_dict = model_to_dict(check, max_depth=1)
            check_json['checks'].append(check_dict)
            check_json['entities'] = entities
            check_json['place'] = place
            smon_id = model_to_dict(check, max_depth=1)
            check_json.update(smon_id['smon_id'])
            check_json.update(model_to_dict(check, recurse=False))
            check_json['name'] = name
            check_json['description'] = description
            if check_json['checks'][i]['smon_id']['check_type'] == 'http':
                check_json['checks'][i]['accepted_status_codes'] = int(check_json['checks'][i]['accepted_status_codes'])
                check_json['accepted_status_codes'] = int(check_json['accepted_status_codes'])
            i += 1
        check_list.append(check_json)
    return check_list


class ChecksView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    def __init__(self):
        self.check_type = None

    def get(self, query: GroupQuery) -> list:
        group_id = SupportClass.return_group_id(query)
        check_type_id = smon_mod.get_check_id_by_name(self.check_type)
        checks = smon_sql.select_multi_checks_with_type(self.check_type, group_id)

        check_list = _return_checks(checks, check_type_id)
        return check_list


class ChecksViewHttp(ChecksView):
    def __init__(self):
        super().__init__()
        self.check_type = 'http'

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Get HTTP list of HTTP checks, for current group or for specific group if {group_id}.
        ---
        tags:
          - 'HTTP Check'
        parameters:
        - in: 'query'
          name: 'group_id'
          description: 'ID of the group to retrieve'
          required: false
          type: 'integer'
        responses:
          '200':
            description: 'A list of HTTP checks'
            schema:
              type: 'array'
              items:
                type: 'object'
                properties:
                  accepted_status_codes:
                    type: 'integer'
                    description: 'Expected HTTP status codes'
                  agent_id:
                    type: 'integer'
                  body:
                    type: 'string'
                    description: 'Response body'
                  body_req:
                    type: 'string'
                    description: 'Request body'
                  body_status:
                    type: 'integer'
                  check_group:
                    type: 'string'
                  check_timeout:
                    type: 'integer'
                    description: 'Timeout for the check'
                  check_type:
                    type: 'string'
                    description: 'Type of check'
                  checks:
                    type: 'array'
                    items:
                      type: 'object'
                      properties:
                        accepted_status_codes:
                          type: 'integer'
                        body:
                          type: 'string'
                        body_req:
                          type: 'string'
                        header_req:
                          type: 'string'
                        ignore_ssl_error:
                          type: 'integer'
                        interval:
                          type: 'integer'
                        method:
                          type: 'string'
                        smon_id:
                          type: 'object'
                          properties:
                            agent_id:
                              type: 'integer'
                            body_status:
                              type: 'integer'
                            check_timeout:
                              type: 'integer'
                            check_type:
                              type: 'string'
                            country_id:
                              type: 'integer'
                            created_at:
                              type: 'string'
                            description:
                              type: 'string'
                            enabled:
                              type: 'integer'
                            group_id:
                              type: 'integer'
                            id:
                              type: 'integer'
                            mm_channel_id:
                              type: 'integer'
                            multi_check_id:
                              type: 'integer'
                            name:
                              type: 'string'
                            pd_channel_id:
                              type: 'integer'
                            region_id:
                              type: 'integer'
                            response_time:
                              type: 'string'
                            slack_channel_id:
                              type: 'integer'
                            ssl_expire_critical_alert:
                              type: 'integer'
                            ssl_expire_date:
                              type: 'string'
                            ssl_expire_warning_alert:
                              type: 'integer'
                            status:
                              type: 'integer'
                            telegram_channel_id:
                              type: 'integer'
                            time_state:
                              type: 'string'
                            updated_at:
                              type: 'string'
                  country_id:
                      type: 'integer'
                  created_at:
                      type: 'string'
                  description:
                      type: 'string'
                  enabled:
                      type: 'integer'
                  entities:
                      type: 'array'
                      items:
                          type: 'integer'
                  group_id:
                      type: 'integer'
                  header_req:
                      type: 'string'
                  id:
                      type: 'integer'
                  ignore_ssl_error:
                      type: 'integer'
                  interval:
                      type: 'integer'
                  method:
                      type: 'string'
                  mm_channel_id:
                      type: 'integer'
                  multi_check_id:
                      type: 'integer'
                  name:
                      type: 'string'
                  pd_channel_id:
                      type: 'integer'
                  place:
                      type: 'string'
                      description: 'Location where checks must be deployed'
                      enum: ['all', 'country', 'region', 'agent']
                  region_id:
                      type: 'integer'
                  response_time:
                      type: 'string'
                  slack_channel_id:
                      type: 'integer'
                  smon_id:
                      type: 'integer'
                  ssl_expire_critical_alert:
                      type: 'integer'
                  ssl_expire_date:
                      type: 'string'
                  ssl_expire_warning_alert:
                      type: 'integer'
                  status:
                      type: 'integer'
                  telegram_channel_id:
                      type: 'integer'
                  time_state:
                      type: 'string'
                  updated_at:
                      type: 'string'
                  url:
                      type: 'string'
        """
        checks = super().get(query)
        return jsonify(checks)


class ChecksViewDns(ChecksView):
    def __init__(self):
        super().__init__()
        self.check_type = 'dns'

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Get DNS list of DNS checks, for current group or for specific group if {group_id}.
        ---
        tags:
          - 'DNS Check'
        parameters:
          - name: 'group_id'
            in: 'query'
            description: 'ID of the group to retrieve'
            required: false
            type: 'integer'
        responses:
          '200':
            description: 'A list of DNS checks'
            schema:
              type: 'array'
              items:
                type: 'object'
                properties:
                  place:
                    type: 'string'
                    description: 'Location where checks must be deployed'
                    enum: ['all', 'country', 'region', 'agent']
                  entities:
                    type: 'array'
                    description: 'List of agents, regions, or countries depending on the place parameter'
                    items:
                      type: 'integer'
                  interval:
                    type: 'integer'
                    description: 'Check interval, in seconds'
                  ip:
                    type: 'string'
                    description: 'IP address for the DNS check'
                  port:
                    type: 'integer'
                    description: 'Port number for the DNS check'
                  record_type:
                    type: 'string'
                    description: 'Type of DNS record for the check'
                  resolver:
                    type: 'string'
                    description: 'DNS resolver for the check'
                  smon_id:
                    type: 'object'
                    description: 'Object containing information related to smon_id'
                    properties:
                      agent_id:
                        type: 'integer'
                      body_status:
                        type: 'integer'
                      check_timeout:
                        type: 'integer'
                      check_type:
                        type: 'string'
                      created_at:
                        type: 'string'
                      description:
                        type: 'string'
                      enabled:
                        type: 'integer'
                      group_id:
                        type: 'integer'
                      id:
                        type: 'integer'
                      mm_channel_id:
                        type: 'integer'
                      multi_check_id:
                        type: 'integer'
                      name:
                        type: 'string'
                      pd_channel_id:
                        type: 'integer'
                      response_time:
                        type: 'string'
                      slack_channel_id:
                        type: 'integer'
                      status:
                        type: 'integer'
                      telegram_channel_id:
                        type: 'integer'
                      time_state:
                        type: 'string'
                      updated_at:
                        type: 'string'
                      region_id:
                        type: 'integer'
                      country_id:
                        type: 'integer'
        """
        checks = super().get(query)
        return jsonify(checks)


class ChecksViewTcp(ChecksView):
    def __init__(self):
        super().__init__()
        self.check_type = 'tcp'

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Get TCP list of TCP checks, for current group or for specific group if {group_id}.
        ---
        tags:
          - 'TCP Check'
        parameters:
          - name: 'group_id'
            in: 'query'
            description: 'ID of the group associated with the TCP checks'
            required: false
            type: 'integer'
        responses:
          '200':
            description: 'A list of TCP checks'
            schema:
              type: 'array'
              items:
                type: 'object'
                properties:
                  agent_id:
                    type: 'integer'
                  body_status:
                    type: 'integer'
                  check_group:
                    type: 'string'
                  check_timeout:
                    type: 'integer'
                    description: 'Timeout for the check'
                  check_type:
                    type: 'string'
                    description: 'Type of check'
                  checks:
                    type: 'array'
                    items:
                      type: 'object'
                      properties:
                        interval:
                          type: 'integer'
                          description: 'Interval for the check'
                        ip:
                          type: 'string'
                          description: 'IP address to check'
                        port:
                          type: 'integer'
                          description: 'Port to check'
                        smon_id:
                          type: 'object'
                          properties:
                            agent_id:
                              type: 'integer'
                            body_status:
                              type: 'integer'
                            check_timeout:
                              type: 'integer'
                            check_type:
                              type: 'string'
                            country_id:
                              type: 'integer'
                            created_at:
                              type: 'string'
                            description:
                              type: 'string'
                            enabled:
                              type: 'integer'
                            group_id:
                              type: 'integer'
                            id:
                              type: 'integer'
                            mm_channel_id:
                              type: 'integer'
                            multi_check_id:
                              type: 'integer'
                            name:
                              type: 'string'
                            pd_channel_id:
                              type: 'integer'
                            region_id:
                              type: 'integer'
                            response_time:
                              type: 'string'
                            slack_channel_id:
                              type: 'integer'
                            ssl_expire_critical_alert:
                              type: 'integer'
                            ssl_expire_date:
                              type: 'string'
                            ssl_expire_warning_alert:
                              type: 'integer'
                            status:
                              type: 'integer'
                            telegram_channel_id:
                              type: 'integer'
                            time_state:
                              type: 'string'
                            updated_at:
                              type: 'string'
                  country_id:
                      type: 'integer'
                  created_at:
                      type: 'string'
                  description:
                      type: 'string'
                  enabled:
                      type: 'integer'
                  entities:
                      type: 'array'
                      items:
                          type: 'integer'
                  group_id:
                      type: 'integer'
                  id:
                      type: 'integer'
                  interval:
                      type: 'integer'
                  ip:
                      type: 'string'
                  mm_channel_id:
                      type: 'integer'
                  multi_check_id:
                      type: 'integer'
                  name:
                      type: 'string'
                  pd_channel_id:
                      type: 'integer'
                  place:
                      type: 'string'
                      description: 'Location where checks must be deployed'
                      enum: ['all', 'country', 'region', 'agent']
                  port:
                      type: 'integer'
                  region_id:
                      type: 'integer'
                  response_time:
                      type: 'string'
                  slack_channel_id:
                      type: 'integer'
                  smon_id:
                      type: 'integer'
                  status:
                      type: 'integer'
                  telegram_channel_id:
                      type: 'integer'
                  time_state:
                      type: 'string'
                  updated_at:
                      type: 'string'
        """
        checks = super().get(query)
        return jsonify(checks)


class ChecksViewPing(ChecksView):
    def __init__(self):
        super().__init__()
        self.check_type = 'ping'

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Get Ping list of Ping checks, for current group or for specific group if {group_id}.
        ---
        tags:
          - 'Ping Check'
        parameters:
          - name: 'group_id'
            in: 'query'
            description: 'ID of the group associated with the Ping checks'
            required: false
            type: 'integer'
        responses:
          '200':
            description: 'ID of the group associated with the Ping checks'
            schema:
              type: 'array'
              items:
                type: 'object'
                properties:
                  place:
                    type: 'string'
                    description: Where checks must be deployed
                    enum: ['all', 'country', 'region', 'agent']
                  entities:
                    type: 'array'
                    description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                    items:
                      type: 'integer'
                  interval:
                    type: 'integer'
                    description: 'Check interval, in seconds'
                  ip:
                    type: 'string'
                    description: 'IP address for the Ping check'
                  packet_size:
                    type: 'integer'
                    description: 'Size of the packet for the Ping check'
                  smon_id:
                    type: 'object'
                    description: 'Object containing information related to smon_id'
                    properties:
                      check_timeout:
                        type: 'integer'
                      check_type:
                        type: 'string'
                      created_at:
                        type: 'string'
                      description:
                        type: 'string'
                      enabled:
                        type: 'string'
                      check_group_id:
                        type: 'integer'
                      id:
                        type: 'integer'
                      mm_channel_id:
                        type: 'integer'
                      name:
                        type: 'string'
                      pd_channel_id:
                        type: 'integer'
                      response_time:
                        type: 'string'
                      slack_channel_id:
                        type: 'integer'
                      status:
                        type: 'integer'
                      telegram_channel_id:
                        type: 'integer'
                      time_state:
                        type: 'string'
                      updated_at:
                        type: 'string'
                      group_id:
                        type: 'integer'
        """
        checks = super().get(query)
        return jsonify(checks)


class ChecksViewSmtp(ChecksView):
    def __init__(self):
        super().__init__()
        self.check_type = 'smtp'

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Get SMTP list of SMTP checks, for current group or for specific group if {group_id}.
        ---
        tags:
          - 'SMTP Check'
        parameters:
          - name: 'group_id'
            in: 'query'
            description: 'ID of the group associated with the Ping checks'
            required: false
            type: 'integer'
        responses:
          '200':
            description: 'A list of SMTP checks'
            schema:
              type: 'array'
              items:
                type: 'object'
                properties:
                  agent_id:
                    type: 'integer'
                  body_status:
                    type: 'integer'
                  check_group:
                    type: 'string'
                  check_timeout:
                    type: 'integer'
                    description: 'Timeout for the check'
                  check_type:
                    type: 'string'
                    description: 'Type of check'
                  checks:
                    type: 'array'
                    items:
                      type: 'object'
                      properties:
                        ignore_ssl_error:
                          type: 'integer'
                          description: 'Flag to ignore SSL errors'
                        interval:
                          type: 'integer'
                          description: 'Interval for the check'
                        ip:
                          type: 'string'
                          description: 'IP address of the SMTP server'
                        password:
                          type: 'string'
                          description: 'SMTP server password'
                        port:
                          type: 'integer'
                          description: 'SMTP server port'
                        smon_id:
                          type: 'object'
                          properties:
                            agent_id:
                              type: 'integer'
                            body_status:
                              type: 'integer'
                            check_timeout:
                              type: 'integer'
                            check_type:
                              type: 'string'
                            country_id:
                              type: 'integer'
                            created_at:
                              type: 'string'
                            description:
                              type: 'string'
                            enabled:
                              type: 'integer'
                            group_id:
                              type: 'integer'
                            id:
                              type: 'integer'
                            mm_channel_id:
                              type: 'integer'
                            multi_check_id:
                              type: 'integer'
                            name:
                              type: 'string'
                            pd_channel_id:
                              type: 'integer'
                            region_id:
                              type: 'integer'
                            response_time:
                              type: 'string'
                            slack_channel_id:
                              type: 'integer'
                            ssl_expire_critical_alert:
                              type: 'integer'
                            ssl_expire_date:
                              type: 'string'
                            ssl_expire_warning_alert:
                              type: 'integer'
                            status:
                              type: 'integer'
                            telegram_channel_id:
                              type: 'integer'
                            time_state:
                              type: 'string'
                            updated_at:
                              type: 'string'
                            use_tls:
                              type: 'integer'
                            username:
                              type: 'string'
                  country_id:
                      type: 'integer'
                  created_at:
                      type: 'string'
                  description:
                      type: 'string'
                  enabled:
                      type: 'integer'
                  entities:
                      type: 'array'
                      items:
                          type: 'integer'
                  group_id:
                      type: 'integer'
                  id:
                      type: 'integer'
                  ignore_ssl_error:
                      type: 'integer'
                  interval:
                      type: 'integer'
                  ip:
                      type: 'string'
                  mm_channel_id:
                      type: 'integer'
                  multi_check_id:
                      type: 'integer'
                  name:
                      type: 'string'
                  password:
                      type: 'string'
                  pd_channel_id:
                      type: 'integer'
                  place:
                      type: 'string'
                      description: 'Location where checks must be deployed'
                      enum: ['all', 'country', 'region', 'agent']
                  port:
                      type: 'integer'
                  region_id:
                      type: 'integer'
                  response_time:
                      type: 'string'
                  slack_channel_id:
                      type: 'integer'
                  smon_id:
                      type: 'integer'
                  status:
                      type: 'integer'
                  telegram_channel_id:
                      type: 'integer'
                  time_state:
                      type: 'string'
                  updated_at:
                      type: 'string'
                  use_tls:
                      type: 'integer'
                  username:
                      type: 'string'
        """
        checks = super().get(query)
        return jsonify(checks)


class ChecksViewRabbit(ChecksView):
    def __init__(self):
        super().__init__()
        self.check_type = 'rabbitmq'

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        """
        Get RabbitMQ list of RabbitMQ checks, for current group or for specific group if {group_id}.
        ---
        tags:
          - 'RabbitMQ Check'
        parameters:
          - name: 'group_id'
            in: 'query'
            description: 'ID of the group associated with the Ping checks'
            required: false
            type: 'integer'
        responses:
          '200':
            description: 'A list of Rabbit checks'
            schema:
              type: 'array'
              items:
                type: 'object'
                properties:
                  agent_id:
                    type: 'integer'
                  body_status:
                    type: 'integer'
                  check_group:
                    type: 'string'
                  check_timeout:
                    type: 'integer'
                    description: 'Timeout for the check'
                  check_type:
                    type: 'string'
                    description: 'Type of check'
                  checks:
                    type: 'array'
                    items:
                      type: 'object'
                      properties:
                        ignore_ssl_error:
                          type: 'integer'
                          description: 'Flag to ignore SSL errors'
                        interval:
                          type: 'integer'
                          description: 'Interval for the check'
                        ip:
                          type: 'string'
                          description: 'IP address of the RabbitMQ server'
                        password:
                          type: 'string'
                          description: 'RabbitMQ server password'
                        port:
                          type: 'integer'
                          description: 'RabbitMQ server port'
                        smon_id:
                          type: 'object'
                          properties:
                            agent_id:
                              type: 'integer'
                            body_status:
                              type: 'integer'
                            check_timeout:
                              type: 'integer'
                            check_type:
                              type: 'string'
                            country_id:
                              type: 'integer'
                            created_at:
                              type: 'string'
                            description:
                              type: 'string'
                            enabled:
                              type: 'integer'
                            group_id:
                              type: 'integer'
                            id:
                              type: 'integer'
                            mm_channel_id:
                              type: 'integer'
                            multi_check_id:
                              type: 'integer'
                            name:
                              type: 'string'
                            pd_channel_id:
                              type: 'integer'
                            region_id:
                              type: 'integer'
                            response_time:
                              type: 'string'
                            slack_channel_id:
                              type: 'integer'
                            ssl_expire_critical_alert:
                              type: 'integer'
                            ssl_expire_date:
                              type: 'string'
                            ssl_expire_warning_alert:
                              type: 'integer'
                            status:
                              type: 'integer'
                            telegram_channel_id:
                              type: 'integer'
                            time_state:
                              type: 'string'
                            updated_at:
                              type: 'string'
                            use_tls:
                              type: 'integer'
                            username:
                              type: 'string'
                  country_id:
                      type: 'integer'
                  created_at:
                      type: 'string'
                  description:
                      type: 'string'
                  enabled:
                      type: 'integer'
                  entities:
                      type: 'array'
                      items:
                          type: 'integer'
                  group_id:
                      type: 'integer'
                  id:
                      type: 'integer'
                  ignore_ssl_error:
                      type: 'integer'
                  interval:
                      type: 'integer'
                  ip:
                      type: 'string'
                  mm_channel_id:
                      type: 'integer'
                  multi_check_id:
                      type: 'integer'
                  name:
                      type: 'string'
                  password:
                      type: 'string'
                  pd_channel_id:
                      type: 'integer'
                  place:
                      type: 'string'
                      description: 'Location where checks must be deployed'
                      enum: ['all', 'country', 'region', 'agent']
                  port:
                      type: 'integer'
                  region_id:
                      type: 'integer'
                  response_time:
                      type: 'string'
                  slack_channel_id:
                      type: 'integer'
                  smon_id:
                      type: 'integer'
                  status:
                      type: 'integer'
                  telegram_channel_id:
                      type: 'integer'
                  time_state:
                      type: 'string'
                  updated_at:
                      type: 'string'
                  use_tls:
                      type: 'integer'
                  username:
                      type: 'string'
        """
        checks = super().get(query)
        return jsonify(checks)


class AllChecksViewWithFilters(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=CheckFiltersQuery)
    def get(self, query: CheckFiltersQuery):
        """
        Get all checks with filters.

        ---
        tags:
        - 'Checks'
        parameters:
        - name: check_group
          in: query
          description: 'Filter by check group.'
          required: false
          type: string
        - name: check_name
          in: query
          description: 'Filter by check name.'
          required: false
          type: string
        - name: check_status
          in: query
          description: 'Filter by check status.'
          required: false
          type: 'integer'
        - name: check_type
          in: query
          description: 'Filter by check type. Available values: `http`, `tcp`, `ping`, `dns`, `rabbitmq`, `smtp`.'
          required: false
          type: string
        - name: sort_by
          in: query
          description: 'Sort checks by check status. If add "-" to a value it will be sorted by ASC. Available values: `name`, `status`, `check_type`, `check_group`, `created_at`, `updated_at`.'
          required: false
          type: 'string'
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
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              type: object
              properties:
                results:
                  type: array
                  description: Array of check objects.
                  items:
                    type: object
                    properties:
                      body_status:
                        type: integer
                        description: The status of the body.
                      check_group:
                        type: string
                        description: The group name of the check (e.g., "edge").
                      check_timeout:
                        type: integer
                        description: The timeout value of the check in seconds.
                      check_type:
                        type: string
                        description: The type of check (e.g., "http", "tcp").
                      created_at:
                        type: string
                        format: date-time
                        description: The date and time when the check was created.
                      current_retries:
                        type: integer
                        description: The number of current retries for this check.
                      description:
                        type: string
                        description: Additional description or information about the check.
                      enabled:
                        type: integer
                        description: Indicates whether the check is enabled (1) or disabled (0).
                      entities:
                        type: array
                        description: List of associated entities.
                        items:
                          type: string
                      group_id:
                        type: integer
                        description: The identifier of the group associated with the check.
                      id:
                        type: integer
                        description: Unique identifier of the check.
                      mm_channel_id:
                        type: integer
                        description: Specific `mm` channel ID where check results are sent.
                      multi_check_id:
                        type: integer
                        description: Identifier for multi-check configurations.
                      name:
                        type: string
                        description: The name of the check.
                      pd_channel_id:
                        type: integer
                        description: PagerDuty channel ID for the check notifications.
                      place:
                        type: string
                        description: The placement or location information for the check (e.g., "all").
                      response_time:
                        type: string
                        format: double
                        description: The average response time recorded for the check.
                      retries:
                        type: integer
                        description: Maximum number of retries configured for the check.
                      slack_channel_id:
                        type: integer
                        description: Slack channel ID for sending check results.
                      ssl_expire_critical_alert:
                        type: integer
                        description: Status of SSL expire critical alerts (0 or 1).
                      ssl_expire_date:
                        type: string
                        format: date-time
                        description: The expiration date of the SSL certificate.
                      ssl_expire_warning_alert:
                        type: integer
                        description: Status of SSL expire warning alerts (0 or 1).
                      status:
                        type: integer
                        description: The current operational status of the check.
                      telegram_channel_id:
                        type: integer
                        description: The Telegram channel ID for check notifications.
                      time_state:
                        type: string
                        format: date-time
                        description: The timestamp of the current check state.
                      updated_at:
                        type: string
                        format: date-time
                        description: The date and time when the check was last updated.
                total:
                  type: integer
                  description: Total number of checks matching the criteria.

        """
        group_id = SupportClass.return_group_id(query)
        checks = smon_sql.select_multi_check_with_filters(group_id, query)
        entities = []
        if any((query.check_name, query.check_group, query.check_type)):
            if query.check_type:
                len_checks = smon_sql.get_count_multi_check_check_type(group_id, query.check_type)
            else:
                len_checks = len(checks)
        elif isinstance(query.check_status, int):
            len_checks = smon_sql.get_count_multi_with_status_checks(group_id, query.check_status)
        else:
            len_checks = smon_sql.get_count_multi_checks(group_id)
        check_list = {'results': [], 'total': len_checks}

        for m in checks:
            check_json = {}
            place = m.multi_check_id.entity_type
            name = m.multi_check_id.name.replace("'", "")
            description = m.multi_check_id.description.replace("'", "")
            if m.multi_check_id.check_group_id:
                group_name = smon_sql.get_smon_group_by_id(m.multi_check_id.check_group_id).name
                group_name = group_name.replace("'", "")
            else:
                group_name = None

            check_json['check_group'] = group_name
            check_json['entities'] = entities
            check_json['place'] = place
            smon_id = model_to_dict(m, recurse=False, exclude={SMON.agent_id, SMON.region_id, SMON.country_id})
            check_json.update(smon_id)
            check_json['name'] = name
            check_json['description'] = description
            check_list['results'].append(check_json)
        return jsonify(check_list)
