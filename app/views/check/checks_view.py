from typing import Union

from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify
from flask_pydantic import validate
from playhouse.shortcuts import model_to_dict

import app.modules.db.smon as smon_sql
from app.modules.common.common_classes import SupportClass
from app.middleware import get_user_params, check_group
from app.modules.db.db_model import SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck, SmonSMTPCheck, SmonRabbitCheck
from app.modules.roxywi.class_models import GroupQuery


class ChecksView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    def __init__(self):
        self.check_type = None

    def get(self, query: GroupQuery) -> Union[SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck]:
        group_id = SupportClass.return_group_id(query)
        checks = smon_sql.select_smon_checks(self.check_type, group_id)
        return checks


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
          required: true
          type: 'integer'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              type: array
              id: 'HttpChecks'
              items:
                properties:
                  smon_id:
                    type: 'object'
                    description: 'RMON object'
                    properties:
                      id:
                        type: 'integer'
                        description: 'RMON ID'
                      name:
                        type: 'string'
                        description: 'Name'
                      port:
                        type: 'integer'
                        description: 'Port'
                      status:
                        type: 'integer'
                        description: 'Status'
                      enabled:
                        type: 'integer'
                        description: 'EN'
                      description:
                        type: 'string'
                        description: 'Description'
                      time_state:
                        type: 'string'
                        format: 'date-time'
                        description: 'Time State'
                  place:
                    type: 'string'
                    description: Where checks must be deployed
                    enum: ['all', 'country', 'region', 'agent']
                  entities:
                    type: 'array'
                    description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                    items:
                      type: 'integer'
                  url:
                    type: 'string'
                    description: 'URL to be tested'
                  method:
                    type: 'string'
                    description: 'HTTP Method to be used'
                  accepted_status_codes:
                    type: 'string'
                    description: 'Expected status code'
                  body:
                    type: 'string'
                    description: 'Body content'
                  interval:
                    type: 'integer'
                    description: 'Timeout interval'
                  headers:
                    type: 'string'
                    description: 'Headers'
                  body_req:
                    type: 'string'
                    description: 'Body Request'
        """
        checks = super().get(query)
        check_list = []
        for check in checks:
            check_list.append(model_to_dict(check, exclude=[SmonHttpCheck.smon_id.http, SmonHttpCheck.smon_id.port]))
        return jsonify(check_list)


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
        check_list = []
        for check in checks:
            check_list.append(model_to_dict(check, exclude=[
                SmonDnsCheck.smon_id.body_status, SmonDnsCheck.smon_id.http, SmonDnsCheck.smon_id.port, SmonDnsCheck.smon_id.ssl_expire_critical_alert,
                SmonDnsCheck.smon_id.ssl_expire_date, SmonDnsCheck.smon_id.ssl_expire_warning_alert
            ]))
        return jsonify(check_list)


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
            description: 'A list of ChecksViewTcp instances'
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
                    description: 'IP address for the TCP check'
                  port:
                    type: 'integer'
                    description: 'Port number for the TCP check'
                  smon_id:
                    type: 'object'
                    description: 'A list of TCP checks'
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
        check_list = []
        for check in checks:
            check_list.append(model_to_dict(check, exclude=[
                SmonTcpCheck.smon_id.body_status, SmonTcpCheck.smon_id.http, SmonTcpCheck.smon_id.port,
                SmonTcpCheck.smon_id.ssl_expire_critical_alert,
                SmonTcpCheck.smon_id.ssl_expire_date, SmonTcpCheck.smon_id.ssl_expire_warning_alert
            ]))
        return jsonify(check_list)


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
        check_list = []
        for check in checks:
            check_list.append(model_to_dict(check, exclude=[
                SmonPingCheck.smon_id.body_status, SmonPingCheck.smon_id.http, SmonPingCheck.smon_id.port,
                SmonPingCheck.smon_id.ssl_expire_critical_alert,
                SmonPingCheck.smon_id.ssl_expire_date, SmonPingCheck.smon_id.ssl_expire_warning_alert
            ]))
        return jsonify(check_list)


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
        check_list = []
        for check in checks:
            check_list.append(model_to_dict(check, exclude=[
                SmonSMTPCheck.smon_id.body_status, SmonSMTPCheck.smon_id.http, SmonSMTPCheck.smon_id.ssl_expire_critical_alert,
                SmonSMTPCheck.smon_id.ssl_expire_date, SmonSMTPCheck.smon_id.ssl_expire_warning_alert
            ]))
        return jsonify(check_list)


class ChecksViewRabbit(ChecksView):
    def __init__(self):
        super().__init__()
        self.check_type = 'smtp'

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
            description: 'ID of the group associated with the RabbitMQ checks'
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
                    description: 'IP address for the RabbitMQ check'
                  port:
                    type: 'integer'
                    description: 'Port for the RabbitMQ check'
                    default: 5672
                  username:
                    type: 'string'
                    description: 'Username for the RabbitMQ check'
                  password:
                    type: 'string'
                    description: 'Password for the RabbitMQ check'
                  vhost:
                    type: 'string'
                    description: 'vhost for the RabbitMQ check'
                    default: /
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
        check_list = []
        for check in checks:
            check_list.append(model_to_dict(check, exclude=[
                SmonRabbitCheck.smon_id.body_status, SmonRabbitCheck.smon_id.http, SmonRabbitCheck.smon_id.ssl_expire_critical_alert,
                SmonRabbitCheck.smon_id.ssl_expire_date, SmonRabbitCheck.smon_id.ssl_expire_warning_alert
            ]))
        return jsonify(check_list)
