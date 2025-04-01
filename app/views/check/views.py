from typing import Union, Tuple

from flask.views import MethodView
from flask_apscheduler.json import jsonify
from flask_jwt_extended import jwt_required
from flask import g, abort
from flask_pydantic import validate
from playhouse.shortcuts import model_to_dict

import app.modules.db.smon as smon_sql
import app.modules.db.region as region_sql
import app.modules.db.country as country_sql
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.smon as smon_mod
import app.modules.tools.smon_agent as smon_agent
from app.middleware import get_user_params, check_group
from app.modules.common.common_classes import SupportClass
from app.modules.roxywi.class_models import (
    IdResponse, HttpCheckRequest, DnsCheckRequest, TcpCheckRequest, PingCheckRequest, BaseResponse, SmtpCheckRequest,
    RabbitCheckRequest, GroupQuery
)
from app.modules.roxywi.exception import RoxywiResourceNotFound


class CheckView(MethodView):
    methods = ["POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    def __init__(self):
        """
        Initialize CheckView instance
        ---
        parameters:
          - name: check_type
            in: path
            type: string
        """
        self.check_type = None
        self.group_id = g.user_params['group_id']
        self.multi_check_func = {
            'country': self._create_country_check,
            'region': self._create_region_check,
            'agent': self._create_agent_check,
        }
        self.create_func = {
            'http': smon_mod.create_http_check,
            'tcp': smon_mod.create_tcp_check,
            'dns': smon_mod.create_dns_check,
            'ping': smon_mod.create_ping_check,
            'smtp': smon_mod.create_smtp_check,
            'rabbitmq': smon_mod.create_rabbit_check,
        }

    def get(self, multi_check_id: int, query: GroupQuery) -> object:
        group_id = SupportClass.return_group_id(query)
        check_type_id = smon_mod.get_check_id_by_name(self.check_type)
        multi_check = smon_sql.select_multi_check(multi_check_id, group_id)
        entities = []
        expiration = ''
        check_json = {'checks': []}
        i = 0

        for m in multi_check:
            place = m.multi_check_id.entity_type
            if m.multi_check_id.runbook:
                runbook = m.multi_check_id.runbook.replace("'", "")
            else:
                runbook = ''
            check_id = m.id
            if m.multi_check_id.check_group_id:
                group_name = smon_sql.get_smon_group_by_id(m.multi_check_id.check_group_id).name
                group_name = group_name.replace("'", "")
            else:
                group_name = None
            if m.multi_check_id.expiration and m.multi_check_id.expiration != '0000-00-00 00:00:00':
                expiration = m.multi_check_id.expiration.strftime("%Y-%m-%d %H:%M")
            check_json['check_group'] = group_name
            if m.country_id:
                entities.append(m.country_id.id)
            elif m.region_id:
                entities.append(m.region_id.id)
            elif m.agent_id:
                entities.append(m.agent_id.id)
            checks = smon_sql.select_one_smon(check_id, check_type_id=check_type_id)
            for check in checks:
                check_dict = model_to_dict(check, max_depth=query.max_depth)
                check_dict['average_response_time'] = smon_mod.get_average_response_time(check_id, check_type_id)
                check_json['checks'].append(check_dict)
                check_json['entities'] = entities
                check_json['place'] = place
                check_json['runbook'] = runbook
                check_json['priority'] = m.multi_check_id.priority
                check_json['expiration'] = expiration
                smon_id = model_to_dict(check, max_depth=query.max_depth)
                check_json.update(smon_id['smon_id'])
                check_json.update(model_to_dict(check, recurse=query.recurse))
                check_json['name'] = check_json['name'].replace("'", "")
                check_json['checks'][i]['smon_id']['name'] = check.smon_id.name.replace("'", "")
                check_json['checks'][i]['smon_id']['uptime'] = smon_mod.check_uptime(check_json['checks'][i]['smon_id']['id'])
                if check_json['checks'][i]['smon_id']['check_type'] == 'http':
                    check_json['checks'][i]['accepted_status_codes'] = int(check_json['checks'][i]['accepted_status_codes'])
                    check_json['accepted_status_codes'] = int(check_json['accepted_status_codes'])
                    check_json['body'] = check.body.replace("'", "")
                i += 1
        if len(check_json['checks']) == 0:
            abort(404, f'{self.check_type} check not found')

        return jsonify(check_json)

    def post(self, data) -> int:
        """

        Handles the post request to create multiple checks.

        Args:
            data: An object containing the required data to create checks.

        Returns:
            The identifier for the created multi-check.

        Raises:
            Exception: If there is an issue with checking the checks limit.
        """
        self.group_id = SupportClass.return_group_id(data)
        try:
            smon_mod.check_checks_limit()
        except Exception as e:
            raise e
        check_parameters = self._return_check_parameters(data)
        check_parameters['group_id'] = self.group_id
        check_parameters['entity_type'] = data.place
        multi_check_id = smon_sql.create_multi_check(**check_parameters)
        if data.place == 'all':
            self._create_all_checks(data, multi_check_id)
        for entity_id in data.entities:
            self.multi_check_func[data.place](data, multi_check_id, entity_id)
        roxywi_common.logger(f'Check {multi_check_id} has been created', keep_history=1, service='RMON')
        return multi_check_id

    def put(self, multi_check_id: int, data) -> None:
        group_id = SupportClass.return_group_id(data)
        new_entities = []
        place = data.place
        check_parameters = self._return_check_parameters(data)
        smon_sql.update_multi_check_group(multi_check_id, **check_parameters)
        if data.place == 'all':
            countries = country_sql.select_enabled_countries_by_group(group_id)
            place = 'country'
            for country in countries:
                regions = region_sql.get_enabled_regions_by_country_with_group(country.id, group_id)
                for _ in regions:
                    new_entities.append(country.id)
        else:
            new_entities = data.entities
        old_entities = []
        entity_id_check_id = {}
        checks = smon_sql.select_multi_check(multi_check_id, group_id)
        for check in checks:
            entity_id, details = self._extract_entity_details(check, data.place)
            old_entities.append(entity_id)
            if entity_id not in entity_id_check_id:
                entity_id_check_id[entity_id] = []
            entity_id_check_id[entity_id].append(details)

        need_to_delete = list(set(old_entities) - set(new_entities))
        need_to_create = list(set(new_entities) - set(old_entities))
        need_to_update = list(set(old_entities) & set(new_entities))
        for entity_id in need_to_delete:
            for check in entity_id_check_id[entity_id]:
                smon_sql.delete_smon(check['check_id'], group_id)
                agent_ip = smon_sql.get_agent_ip_by_id(check['agent_id'])
                smon_agent.delete_check(check['agent_id'], agent_ip, check['check_id'])
                roxywi_common.logger(f'Check {check["check_id"]} has been deleted from Agent {check["agent_id"]}')
        for entity_id in need_to_update:
            for check in entity_id_check_id[entity_id]:
                try:
                    smon_mod.update_smon(check['check_id'], data)
                    self._create_agent_check(
                        data,
                        multi_check_id,
                        check['agent_id'],
                        check['region_id'],
                        check['country_id'],
                        check_id=check['check_id']
                    )
                except Exception as e:
                    raise Exception(f'Cannot update {self.check_type}, id {multi_check_id}: {e}')
        for entity_id in need_to_create:
            if place == 'all':
                self._create_all_checks(data, multi_check_id)
            else:
                try:
                    self.multi_check_func[place](data, multi_check_id, entity_id)
                except Exception as e:
                    raise Exception(f'here: {e}')
        roxywi_common.logger(f'Check {multi_check_id} has been updated', keep_history=1, service='RMON')

    def delete(self, check_id: int, query: GroupQuery) -> Union[int, tuple]:
        group_id = SupportClass.return_group_id(query)
        try:
            smon_mod.delete_multi_check(check_id, group_id)
            roxywi_common.logger(f'Check {check_id} has been deleted', keep_history=1, service='RMON')
            return BaseResponse(status='Ok').model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot delete {self.check_type} check')

    def _return_check_parameters(self, data) -> dict:
        check_parameters = {
            'check_group_id': self._get_check_group_id(data.check_group),
            'runbook': data.runbook,
            'priority': data.priority,
            'expiration': data.expiration
        }
        return check_parameters

    def _create_all_checks(self, data, multi_check_id: int):
        countries = country_sql.select_enabled_countries_by_group(self.group_id)

        if len(countries) == 0:
            # Delete created empty multi check
            smon_sql.delete_multi_check(multi_check_id, self.group_id)
            raise Exception('There are no countries in your group')
        for c in countries:
            self._create_country_check(data, multi_check_id, c.id)
            roxywi_common.logger(f'A new check {data.name.encode("utf-8")} has been created on Country {c.name}')

    def _create_country_check(self, data, multi_check_id: int, country_id: int):
        regions = region_sql.get_enabled_regions_by_country_with_group(country_id, self.group_id)
        if len(regions) == 0:
            # Delete created empty multi check
            smon_sql.delete_multi_check(multi_check_id, self.group_id)
            raise Exception(f'There are no regions in your group in country_id: {country_id}')
        for region in regions:
            self._create_region_check(data, multi_check_id, region.id, country_id)
            roxywi_common.logger(f'A new check {data.name.encode("utf-8")} has been created on Region {region.name}')

    def _create_region_check(self, data, multi_check_id: int, region_id: int, country_id: int = None):
        try:
            random_agent_id = smon_sql.get_randon_agent(region_id)
        except RoxywiResourceNotFound:
            if not country_id:
                raise Exception(f'There are no agents in the region_id: {region_id}')
            pass
        except Exception as e:
            raise Exception(f'Cannot get agent from region: {e}')
        else:
            self._create_agent_check(data, multi_check_id, random_agent_id, region_id, country_id)

    def _create_agent_check(self, data, multi_check_id: int, agent_id, region_id: int = None, country_id: int = None, check_id: int = None):
        if check_id is None:
            try:
                last_id = smon_mod.create_check(data, self.group_id, self.check_type, multi_check_id, agent_id, region_id, country_id)
            except Exception as e:
                raise e
        else:
            last_id = check_id

        try:
            self.create_func[self.check_type](data, last_id)
            if data.enabled:
                smon_mod.send_new_check(last_id, data, agent_id)
        except Exception as e:
            raise e

    @staticmethod
    def _extract_entity_details(check, data_place: str) -> Tuple[int, dict]:
        country_id = check.country_id.id if check.country_id else None
        region_id = check.region_id.id if check.region_id else None
        if data_place in ('all', 'country'):
            entity_id = check.country_id.id
        elif data_place == 'region':
            entity_id = check.region_id.id
        elif data_place == 'agent':
            entity_id = check.agent_id.id
        return entity_id, {
            'check_id': check.id,
            'country_id': country_id,
            'region_id': region_id,
            'agent_id': check.agent_id.id
        }

    def _get_check_group_id(self, check_group_name: str) -> Union[int, None]:
        if check_group_name:
            check_group_id = smon_sql.get_smon_group_by_name(self.group_id, check_group_name)
            if not check_group_id:
                return smon_sql.add_smon_group(self.group_id, check_group_name)
            else:
                return check_group_id
        else:
            return None


class CheckHttpView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'http'

    @validate(query=GroupQuery)
    def get(self, check_id: int, query: GroupQuery) -> object:
        """
        Get HTTP check.
        ---
        tags:
        - 'HTTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'HttpCheck'
              properties:
                checks:
                  type: 'array'
                  description: 'List of checks inside multicheck'
                  items:
                    type: 'object'
                    properties:
                      accepted_status_codes:
                        type: 'string'
                        description: 'Expected status code'
                      body:
                        type: 'string'
                        description: 'Body content'
                      body_req:
                        type: 'string'
                        description: 'Body Request'
                      headers:
                        type: 'string'
                        description: 'Headers'
                      ignore_ssl_error:
                        type: 'integer'
                        description: 'Ignore TLS/SSL error'
                      interval:
                        type: 'integer'
                        description: 'Timeout interval'
                      method:
                        type: 'string'
                        description: 'HTTP Method to be used'
                      uptime:
                         type: 'integer'
                         description: 'Check uptime'
                      smon_id:
                        type: 'object'
                        description: 'RMON object'
                        properties:
                          body_status:
                            type: 'integer'
                            description: 'Body Status'
                          check_timeout:
                            type: 'integer'
                            description: 'Check Timeout'
                          check_type:
                            type: 'string'
                            description: 'Check Type'
                          country_id:
                            type: 'integer'
                            description: 'Country ID'
                          created_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Creation Time'
                          description:
                            type: 'string'
                            description: 'Description'
                          enabled:
                            type: 'integer'
                            description: 'Enabled status'
                          check_group:
                            type: 'string'
                            description: 'Name of the check group'
                          id:
                            type: 'integer'
                            description: 'ID'
                          mm_channel_id:
                            type: 'integer'
                            description: 'MM Channel ID'
                          email_channel_id:
                            type: 'integer'
                            description: 'Email Channel ID'
                          multi_check_id:
                            type: 'integer'
                            description: 'Multi-check ID'
                          name:
                            type: 'string'
                            description: 'Name'
                          pd_channel_id:
                            type: 'integer'
                            description: 'PD Channel ID'
                          region_id:
                            type: 'integer'
                            description: 'Region ID'
                          response_time:
                            type: 'string'
                            description: 'Response Time'
                          slack_channel_id:
                            type: 'integer'
                            description: 'Slack Channel ID'
                          ssl_expire_critical_alert:
                            type: 'integer'
                            description: 'SSL Expire Critical Alert'
                          ssl_expire_date:
                            type: 'string'
                            format: 'date-time'
                            description: 'SSL Expiry Date'
                          ssl_expire_warning_alert:
                            type: 'integer'
                            description: 'SSL Expire Warning Alert'
                          status:
                            type: 'integer'
                            description: 'Status'
                          telegram_channel_id:
                            type: 'integer'
                            description: 'Telegram Channel ID'
                          time_state:
                            type: 'string'
                            format: 'date-time'
                            description: 'Time State'
                          updated_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Update Time'
                          group_id:
                            type: 'integer'
                            description: 'User Group'
                      url:
                        type: 'string'
                        description: 'URL to be tested'
                enabled:
                  type: 'integer'
                  description: 'Enable status (1 for enabled)'
                place:
                  type: 'string'
                  description: 'Where checks must be deployed'
                  enum: ['all', 'country', 'region', 'agent']
                entities:
                  type: 'array'
                  description: 'List of agents, regions, or countries. What exactly will be chosen depends on the place parameter'
                  items:
                    type: 'integer'
                group_name:
                  type: 'string'
                  description: 'Group Name'
                retries:
                  type: 'integer'
                  description: 'Maximum retries before the service is marked as down and a notification is sent'
                  default: 3
                redirects:
                  type: 'integer'
                  description: 'Maximum number of redirects to follow. Set to 0 to disable redirects.'
                  default: 10
                runbook:
                  type: 'string'
                  description: 'Link to runbook'
                priority:
                  type: 'string'
                  description: 'Alert priority'
                  default: 'critical'
                expiration:
                  type: 'string'
                  description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        """
        return super().get(check_id, query)

    @validate(body=HttpCheckRequest)
    def post(self, body: HttpCheckRequest) -> Union[dict, tuple]:
        """
        Create new HTTP check
        ---
        tags:
        - 'HTTP Check'
        parameters:
        - in: 'body'
          name: 'body'
          description: 'HTTP check details'
          required: true
          schema:
            id: 'CheckHttpDetails'
            required:
              - name
              - enabled
              - url
              - method
              - place
              - entities
            properties:
              name:
                type: 'string'
                description: 'Check name'
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
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
              body:
                type: 'string'
                description: 'Body content (optional)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              method:
                type: 'string'
                description: 'HTTP method'
                enum: ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              body_req:
                type: 'string'
                description: 'Body Request (optional)'
              header_req:
                type: 'string'
                description: 'Header Request (optional)'
              accepted_status_codes:
                type: 'integer'
                description: 'Expected status code (default to 200, optional)'
                minimum: 100
                maximum: 599
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              ignore_ssl_error:
                type: 'integer'
                description: 'Ignore TLS/SSL error'
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              redirects:
                type: 'integer'
                description: 'Maximum number of redirects to follow. Set to 0 to disable redirects.'
                default: 10
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'CheckHttpResponse'
              properties:
                id:
                  type: 'string'
                  description: 'ID of the created test case'
        """
        try:
            last_id = super().post(body)
            return IdResponse(id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, '')

    @validate(body=HttpCheckRequest)
    def put(self, check_id: int, body: HttpCheckRequest) -> Union[dict, tuple]:
        """
        Update HTTP check
        ---
        tags:
        - 'HTTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to update'
          required: true
          type: 'integer'
        - in: 'body'
          name: 'body'
          description: 'Object to be updated'
          required: true
          schema:
            id: 'HttpCheckRequest'
            properties:
              name:
                type: 'string'
                description: 'Check name'
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
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
              body:
                type: 'string'
                description: 'Body content (optional)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              method:
                  type: 'string'
                  description: 'HTTP method'
                  enum: ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              body_req:
                type: 'string'
                description: 'Body Request (optional)'
              header_req:
                type: 'string'
                description: 'Header Request (optional)'
              accepted_status_codes:
                type: 'integer'
                description: 'Expected status code (default to 200, optional)'
                minimum: 100
                maximum: 599
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              ignore_ssl_error:
                type: 'integer'
                description: 'Ignore TLS/SSL error'
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              redirects:
                type: 'integer'
                description: 'Maximum number of redirects to follow. Set to 0 to disable redirects.'
                default: 10
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '201':
            description: 'Successful Operation, HTTP Check updated'
          '404':
            description: 'HTTP Check not found'
        """
        try:
            super().put(check_id, body)
            return BaseResponse().model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot update {self.check_type} check')

    @validate(query=GroupQuery)
    def delete(self, check_id: int, query: GroupQuery) -> Union[dict, tuple]:
        """
        Delete check
        ---
        tags:
        - 'HTTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to delete'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id, query)


class CheckTcpView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'tcp'

    @validate(query=GroupQuery)
    def get(self, check_id: int, query: GroupQuery) -> object:
        """
        Get TCP check.
        ---
        tags:
        - 'TCP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'TcpCheck'
              properties:
                checks:
                  type: 'array'
                  description: 'List of checks inside multicheck'
                  items:
                    type: 'object'
                    properties:
                      interval:
                        type: 'integer'
                        description: 'Timeout interval'
                      ip:
                        type: 'string'
                        description: 'IP address to be tested'
                      port:
                        type: 'integer'
                        description: 'Port to be tested'
                      average_response_time:
                        type: 'integer'
                        description: 'Average response time in ms'
                      uptime:
                         type: 'integer'
                         description: 'Check uptime'
                      uptime:
                         type: 'integer'
                         description: 'Check uptime'
                      smon_id:
                        type: 'object'
                        description: 'RMON object'
                        properties:
                          check_timeout:
                            type: 'integer'
                            description: 'Check Timeout'
                          check_type:
                            type: 'string'
                            description: 'Check Type'
                          country_id:
                            type: 'integer'
                            description: 'Country ID'
                          created_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Creation Time'
                          description:
                            type: 'string'
                            description: 'Description'
                          enabled:
                            type: 'integer'
                            description: 'Enabled status'
                          check_group:
                            type: 'string'
                            description: 'Name of check group (optional)'
                          id:
                            type: 'integer'
                            description: 'ID'
                          mm_channel_id:
                            type: 'integer'
                            description: 'MM Channel ID'
                          email_channel_id:
                            type: 'integer'
                            description: 'Email channel ID (optional)'
                          multi_check_id:
                            type: 'integer'
                            description: 'Multi-check ID'
                          name:
                            type: 'string'
                            description: 'Name'
                          pd_channel_id:
                            type: 'integer'
                            description: 'PD Channel ID'
                          region_id:
                            type: 'integer'
                            description: 'Region ID'
                          response_time:
                            type: 'string'
                            description: 'Response Time'
                          slack_channel_id:
                            type: 'integer'
                            description: 'Slack Channel ID'
                          status:
                            type: 'integer'
                            description: 'Status'
                          telegram_channel_id:
                            type: 'integer'
                            description: 'Telegram Channel ID'
                          time_state:
                            type: 'string'
                            format: 'date-time'
                            description: 'Time State'
                          updated_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Update Time'
                          group_id:
                            type: 'integer'
                            description: 'User Group'
                entities:
                  type: 'array'
                  description: 'List of agents, regions, or countries. What exactly will be chosen depends on the place parameter'
                  items:
                    type: 'integer'
                group_name:
                  type: 'string'
                  description: 'Group Name'
                place:
                  type: 'string'
                  description: 'Where checks must be deployed'
                  enum: ['all', 'country', 'region', 'agent']
                retries:
                  type: 'integer'
                  description: 'Maximum retries before the service is marked as down and a notification is sent'
                  default: 3
                runbook:
                  type: 'string'
                  description: 'Link to runbook'
                priority:
                  type: 'string'
                  description: 'Alert priority'
                  default: 'critical'
                expiration:
                  type: 'string'
                  description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        """
        return super().get(check_id, query)

    @validate(body=TcpCheckRequest)
    def post(self, body: TcpCheckRequest) -> Union[dict, tuple]:
        """
        Create a new TCP check
        ---
        tags:
        - 'TCP Check'
        parameters:
        - in: 'body'
          name: 'body'
          description: 'TCP Check Details'
          required: true
          schema:
            id: 'CheckTcpDetails'
            required:
              - name
              - ip
              - port
              - enabled
              - place
              - entities
              - priority
            properties:
              name:
                type: 'string'
                description: 'Name of the test tcp'
              ip:
                type: 'string'
                description: 'IP address or domain name for the TCP check'
              port:
                type: 'integer'
                description: 'Port number'
                minimum: 1
                maximum: 65535
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                 type: 'array'
                 description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                 items:
                   type: 'integer'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              interval:
                type: 'integer'
                description: 'Interval check (default to 120, optional)'
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'CheckTcpResponse'
              properties:
                id:
                  type: 'string'
                  description: 'ID of the created test case'
        """
        try:
            last_id = super().post(body)
            return IdResponse(status='Ok', id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, '')

    @validate(body=TcpCheckRequest)
    def put(self, check_id: int, body: TcpCheckRequest) -> Union[dict, tuple]:
        """
        Update TCP check
        ---
        tags:
        - 'TCP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to update'
          required: true
          type: 'integer'
        - in: 'body'
          name: 'body'
          description: 'Object to be updated'
          required: true
          schema:
            id: 'TcpCheckRequest'
            properties:
              name:
                type: 'string'
                description: 'Name of the test tcp'
              ip:
                type: 'string'
                description: 'IP address or domain name for the TCP check'
              port:
                type: 'integer'
                description: 'Port number'
                minimum: 1
                maximum: 65535
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                 type: 'array'
                 description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                 items:
                   type: 'integer'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              interval:
                type: 'integer'
                description: 'Interval check (default to 120, optional)'
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '201':
            description: 'Successful Operation, TCP Check updated'
          '404':
            description: 'TCP Check not found'
        """
        try:
            super().put(check_id, body)
            return BaseResponse(status='Ok').model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot update {self.check_type} check')

    @validate(query=GroupQuery)
    def delete(self, check_id: int, query: GroupQuery) -> Union[dict, tuple]:
        """
        Delete check
        ---
        tags:
        - 'TCP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to delete'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id, query)


class CheckDnsView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'dns'

    @validate(query=GroupQuery)
    def get(self, check_id: int, query: GroupQuery) -> object:
        """
        Get DNS check or list of DNS checks, if without {check_id}.
        ---
        tags:
        - 'DNS Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'SmonDnsCheck'
              properties:
                checks:
                  type: 'array'
                  description: 'List of checks inside multicheck'
                  items:
                    type: 'object'
                    properties:
                      interval:
                        type: 'integer'
                        description: 'Timeout interval'
                      ip:
                        type: 'string'
                        description: 'IP address to be tested'
                      port:
                        type: 'integer'
                        description: 'Port to be tested'
                      average_response_time:
                        type: 'integer'
                        description: 'Average response time in ms'
                      uptime:
                         type: 'integer'
                         description: 'Check uptime'
                      smon_id:
                        type: 'object'
                        description: 'RMON object'
                        properties:
                          check_timeout:
                            type: 'integer'
                            description: 'Check Timeout'
                          check_type:
                            type: 'string'
                            description: 'Check Type'
                          country_id:
                            type: 'integer'
                            description: 'Country ID'
                          created_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Creation Time'
                          description:
                            type: 'string'
                            description: 'Description'
                          enabled:
                            type: 'integer'
                            description: 'Enabled status'
                          check_group:
                            type: 'string'
                            description: 'Name of check group (optional)'
                          id:
                            type: 'integer'
                            description: 'ID'
                          mm_channel_id:
                            type: 'integer'
                            description: 'MM Channel ID'
                          email_channel_id:
                            type: 'integer'
                            description: 'Email channel ID (optional)'
                          multi_check_id:
                            type: 'integer'
                            description: 'Multi-check ID'
                          name:
                            type: 'string'
                            description: 'Name'
                          pd_channel_id:
                            type: 'integer'
                            description: 'PD Channel ID'
                          region_id:
                            type: 'integer'
                            description: 'Region ID'
                          response_time:
                            type: 'string'
                            description: 'Response Time'
                          slack_channel_id:
                            type: 'integer'
                            description: 'Slack Channel ID'
                          status:
                            type: 'integer'
                            description: 'Status'
                          telegram_channel_id:
                            type: 'integer'
                            description: 'Telegram Channel ID'
                          time_state:
                            type: 'string'
                            format: 'date-time'
                            description: 'Time State'
                          updated_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Update Time'
                          group_id:
                            type: 'integer'
                            description: 'User Group'
                place:
                  type: 'string'
                  description: Where checks must be deployed
                  enum: ['all', 'country', 'region', 'agent']
                entities:
                   type: 'array'
                   description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                   items:
                     type: 'integer'
                ip:
                  type: 'string'
                  description: 'IP address to be tested'
                port:
                  type: 'integer'
                  description: 'Port to be tested'
                resolver:
                  type: 'string'
                  description: 'Resolver to be tested'
                record_type:
                  type: 'string'
                  description: 'Type of DNS record to check'
                interval:
                  type: 'integer'
                  description: 'Check interval'
                retries:
                  type: 'integer'
                  description: 'Maximum retries before the service is marked as down and a notification is sent'
                  default: 3
                runbook:
                  type: 'string'
                  description: 'Link to runbook'
                priority:
                  type: 'string'
                  description: 'Alert priority'
                  default: 'critical'
                expiration:
                  type: 'string'
                  description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        """
        return super().get(check_id, query)

    @validate(body=DnsCheckRequest)
    def post(self, body: DnsCheckRequest) -> Union[dict, tuple]:
        """
        Create DNS check
        ---
        tags:
        - 'DNS Check'
        parameters:
        - in: 'body'
          name: 'body'
          description: 'DNS Check Details'
          required: true
          schema:
            id: 'CheckDnsDetails'
            required:
              - name
              - ip
              - resolver
              - record_type
              - enabled
              - place
              - entities
            properties:
              name:
                type: 'string'
                description: 'Name of the test dns'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                 type: 'array'
                 description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                 items:
                   type: 'integer'
              ip:
                type: 'string'
                description: 'Resolver IP address or domain name'
              port:
                type: 'integer'
                description: 'Port number for DNS resolver (default to 53, optional)'
                minimum: 1
                maximum: 65535
                default: 53
              resolver:
                type: 'string'
                description: 'DNS resolver'
              record_type:
                type: 'string'
                description: 'DNS record type (a, aaa, caa, cname, mx, ns, ptr, sao, src, txt)'
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'CheckDnsResponse'
              properties:
                id:
                  type: 'string'
                  description: 'ID of the created test case'
        """
        try:
            last_id = super().post(body)
            return IdResponse(status='Ok', id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, '')

    @validate(body=DnsCheckRequest)
    def put(self, check_id: int, body: DnsCheckRequest) -> Union[dict, tuple]:
        """
        Update DNS check
        ---
        tags:
        - 'DNS Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to update'
          required: true
          type: 'integer'
        - in: 'body'
          name: 'body'
          description: 'Object to be updated'
          required: true
          schema:
            id: 'DnsCheckRequest'
            properties:
              name:
                type: 'string'
                description: 'Name of the test dns'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                type: 'array'
                description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                items:
                  type: 'integer'
              ip:
                type: 'string'
                description: 'Resolver IP address or domain name'
              port:
                type: 'integer'
                description: 'Port number for DNS resolver (default to 53, optional)'
                minimum: 1
                maximum: 65535
                default: 53
              resolver:
                type: 'string'
                description: 'DNS resolver'
              record_type:
                type: 'string'
                description: 'DNS record type (a, aaa, caa, cname, mx, ns, ptr, sao, src, txt)'
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '201':
            description: 'Successful Operation, DNS Check updated'
          '404':
            description: 'DNS Check not found'
        """
        try:
            super().put(check_id, body)
            return BaseResponse(status='Ok').model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot update {self.check_type} check')

    @validate(query=GroupQuery)
    def delete(self, check_id: int, query: GroupQuery) -> Union[dict, tuple]:
        """
        Delete check
        ---
        tags:
        - 'DNS Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to delete'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id, query)


class CheckPingView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'ping'

    @validate(query=GroupQuery)
    def get(self, check_id: int, query: GroupQuery) -> object:
        """
        Get Ping check or list of Ping checks, if without {check_id}.
        ---
        tags:
        - 'Ping Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'PingCheckDetails'
              properties:
                checks:
                  type: 'array'
                  description: 'List of checks inside multicheck'
                  items:
                    type: 'object'
                    properties:
                      interval:
                        type: 'integer'
                        description: 'Timeout interval'
                      ip:
                        type: 'string'
                        description: 'IP address to be tested'
                      port:
                        type: 'integer'
                        description: 'Port to be tested'
                      average_response_time:
                        type: 'integer'
                        description: 'Average response time in ms'
                      uptime:
                         type: 'integer'
                         description: 'Check uptime'
                      smon_id:
                        type: 'object'
                        description: 'RMON object'
                        properties:
                          check_timeout:
                            type: 'integer'
                            description: 'Check Timeout'
                          check_type:
                            type: 'string'
                            description: 'Check Type'
                          country_id:
                            type: 'integer'
                            description: 'Country ID'
                          created_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Creation Time'
                          description:
                            type: 'string'
                            description: 'Description'
                          enabled:
                            type: 'integer'
                            description: 'Enabled status'
                          check_group:
                            type: 'string'
                            description: 'Name of check group (optional)'
                          id:
                            type: 'integer'
                            description: 'ID'
                          mm_channel_id:
                            type: 'integer'
                            description: 'MM Channel ID'
                          email_channel_id:
                            type: 'integer'
                            description: 'Email channel ID (optional)'
                          multi_check_id:
                            type: 'integer'
                            description: 'Multi-check ID'
                          name:
                            type: 'string'
                            description: 'Name'
                          pd_channel_id:
                            type: 'integer'
                            description: 'PD Channel ID'
                          region_id:
                            type: 'integer'
                            description: 'Region ID'
                          response_time:
                            type: 'string'
                            description: 'Response Time'
                          slack_channel_id:
                            type: 'integer'
                            description: 'Slack Channel ID'
                          status:
                            type: 'integer'
                            description: 'Status'
                          telegram_channel_id:
                            type: 'integer'
                            description: 'Telegram Channel ID'
                          time_state:
                            type: 'string'
                            format: 'date-time'
                            description: 'Time State'
                          updated_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Update Time'
                          group_id:
                            type: 'integer'
                            description: 'User Group'
                place:
                  type: 'string'
                  description: Where checks must be deployed
                  enum: ['all', 'country', 'region', 'agent']
                entities:
                  type: 'array'
                  description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                  items:
                    type: 'integer'
                ip:
                  type: 'string'
                  description: 'IP address to be tested'
                packet_size:
                  type: 'integer'
                  description: 'Size of the packet to be sent'
                interval:
                  type: 'integer'
                  description: 'Ping interval'
                retries:
                  type: 'integer'
                  description: 'Maximum retries before the service is marked as down and a notification is sent'
                  default: 3
                runbook:
                  type: 'string'
                  description: 'Link to runbook'
                priority:
                  type: 'string'
                  description: 'Alert priority'
                  default: 'critical'
                expiration:
                  type: 'string'
                  description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        """
        return super().get(check_id, query)

    @validate(body=PingCheckRequest)
    def post(self, body: PingCheckRequest) -> Union[dict, tuple]:
        """
        Create a new Ping check
        ---
        tags:
        - 'Ping Check'
        parameters:
        - in: 'body'
          name: 'body'
          description: 'Ping Check Details'
          required: true
          schema:
            id: 'CheckPingDetails'
            required:
              - name
              - ip
              - enabled
              - place
              - entities
            properties:
              name:
                type: 'string'
                description: 'Check name'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                type: 'array'
                description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                items:
                  type: 'integer'
              ip:
                type: 'string'
                description: 'IP address or domain name for Ping check'
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              packet_size:
                type: 'integer'
                description: 'Packet size (optional)'
                default: 56
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'CheckPingResponse'
              properties:
                id:
                  type: 'integer'
                  description: 'ID of the created test case'
        """
        try:
            last_id = super().post(body)
            return IdResponse(status='Ok', id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, '')

    @validate(body=PingCheckRequest)
    def put(self, check_id: int, body: PingCheckRequest) -> Union[dict, tuple]:
        """
        Update Ping check
        ---
        tags:
        - 'Ping Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to update'
          required: true
          type: 'integer'
        - in: 'body'
          name: 'body'
          description: 'Object to be updated'
          required: true
          schema:
            id: 'SmonPingCheck'
            properties:
              name:
                type: 'string'
                description: 'Check name'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                type: 'array'
                description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                items:
                  type: 'integer'
              ip:
                type: 'string'
                description: 'IP address or domain name for Ping check'
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              packet_size:
                type: 'integer'
                description: 'Packet size (optional)'
                default: 56
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              region_id:
                type: 'integer'
                description: 'Region ID'
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '201':
            description: 'Successful Operation, Ping Check updated'
          '404':
            description: 'Ping Check not found'
        """
        try:
            super().put(check_id, body)
            return BaseResponse(status='Ok').model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot update {self.check_type} check')

    @validate(query=GroupQuery)
    def delete(self, check_id: int, query: GroupQuery) -> Union[dict, tuple]:
        """
        Delete check
        ---
        tags:
        - 'Ping Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to delete'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id, query)


class CheckSmtpView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'smtp'

    @validate(query=GroupQuery)
    def get(self, check_id: int, query: GroupQuery) -> object:
        """
        Get SMTP check or list of SMTP checks, if without {check_id}.
        ---
        tags:
        - 'SMTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'SMTPCheckDetails'
              properties:
                checks:
                  type: 'array'
                  description: 'List of checks inside multicheck'
                  items:
                    type: 'object'
                    properties:
                      interval:
                        type: 'integer'
                        description: 'Timeout interval'
                      ip:
                        type: 'string'
                        description: 'IP address to be tested'
                      port:
                        type: 'integer'
                        description: 'Port to be tested'
                      average_response_time:
                        type: 'integer'
                        description: 'Average response time in ms'
                      uptime:
                         type: 'integer'
                         description: 'Check uptime'
                      smon_id:
                        type: 'object'
                        description: 'RMON object'
                        properties:
                          check_timeout:
                            type: 'integer'
                            description: 'Check Timeout'
                          check_type:
                            type: 'string'
                            description: 'Check Type'
                          country_id:
                            type: 'integer'
                            description: 'Country ID'
                          created_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Creation Time'
                          description:
                            type: 'string'
                            description: 'Description'
                          enabled:
                            type: 'integer'
                            description: 'Enabled status'
                          check_group:
                            type: 'string'
                            description: 'Name of check group (optional)'
                          id:
                            type: 'integer'
                            description: 'ID'
                          mm_channel_id:
                            type: 'integer'
                            description: 'MM Channel ID'
                          email_channel_id:
                            type: 'integer'
                            description: 'Email channel ID (optional)'
                          multi_check_id:
                            type: 'integer'
                            description: 'Multi-check ID'
                          name:
                            type: 'string'
                            description: 'Name'
                          pd_channel_id:
                            type: 'integer'
                            description: 'PD Channel ID'
                          region_id:
                            type: 'integer'
                            description: 'Region ID'
                          response_time:
                            type: 'string'
                            description: 'Response Time'
                          slack_channel_id:
                            type: 'integer'
                            description: 'Slack Channel ID'
                          status:
                            type: 'integer'
                            description: 'Status'
                          telegram_channel_id:
                            type: 'integer'
                            description: 'Telegram Channel ID'
                          time_state:
                            type: 'string'
                            format: 'date-time'
                            description: 'Time State'
                          updated_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Update Time'
                          group_id:
                            type: 'integer'
                            description: 'User Group'
                place:
                  type: 'string'
                  description: Where checks must be deployed
                  enum: ['all', 'country', 'region', 'agent']
                entities:
                  type: 'array'
                  description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                  items:
                    type: 'integer'
                ip:
                  type: 'string'
                  description: 'SMTP server to be tested'
                username:
                  type: 'integer'
                  description: 'Username to connect to the SMTP server'
                interval:
                  type: 'integer'
                  description: 'Ping interval'
                ignore_ssl_error:
                  type: 'integer'
                  description: 'Ignore TLS/SSL error'
                retries:
                  type: 'integer'
                  description: 'Maximum retries before the service is marked as down and a notification is sent'
                  default: 3
                runbook:
                  type: 'string'
                  description: 'Link to runbook'
                priority:
                  type: 'string'
                  description: 'Alert priority'
                  default: 'critical'
                expiration:
                  type: 'string'
                  description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        """
        return super().get(check_id, query)

    @validate(body=SmtpCheckRequest)
    def post(self, body: SmtpCheckRequest) -> Union[dict, tuple]:
        """
        Create a new SMTP check
        ---
        tags:
        - 'SMTP Check'
        parameters:
        - in: 'body'
          name: 'body'
          description: 'SMTP Check Details'
          required: true
          schema:
            id: 'CheckSMTPDetails'
            required:
              - name
              - ip
              - port
              - username
              - password
              - enabled
              - place
              - entities
            properties:
              name:
                type: 'string'
                description: 'Check name'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                type: 'array'
                description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                items:
                  type: 'integer'
              ip:
                type: 'string'
                description: 'IP address or domain name for SMTP server check'
              port:
                type: 'integer'
                description: 'Port of SMTP server'
                default: 587
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              username:
                type: 'string'
                description: 'Username to connect to the SMTP server'
              password:
                type: 'string'
                description: 'Password to connect to the SMTP server'
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              ignore_ssl_error:
                type: 'integer'
                description: 'Ignore TLS/SSL error'
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'CheckSMTPResponse'
              properties:
                id:
                  type: 'string'
                  description: 'ID of the created test case'
        """
        try:
            last_id = super().post(body)
            return IdResponse(status='Ok', id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, '')

    @validate(body=SmtpCheckRequest)
    def put(self, check_id: int, body: SmtpCheckRequest) -> Union[dict, tuple]:
        """
        Update SMTP check
        ---
        tags:
        - 'SMTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to update'
          required: true
          type: 'integer'
        - in: 'body'
          name: 'body'
          description: 'Object to be updated'
          required: true
          schema:
            id: 'SmonSMTPCheck'
            properties:
              name:
                type: 'string'
                description: 'Check name'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                type: 'array'
                description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                items:
                  type: 'integer'
              ip:
                type: 'string'
                description: 'IP address or domain of SMTP server check'
              port:
                type: 'integer'
                description: 'Port of SMTP server'
                default: 587
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              username:
                type: 'string'
                description: 'Username to connect to the SMTP server'
              password:
                type: 'string'
                description: 'Password to connect to the SMTP server'
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              ignore_ssl_error:
                type: 'integer'
                description: 'Ignore TLS/SSL error'
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '201':
            description: 'Successful Operation, Ping Check updated'
          '404':
            description: 'Ping Check not found'
        """
        try:
            super().put(check_id, body)
            return BaseResponse(status='Ok').model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot update {self.check_type} check')

    @validate(query=GroupQuery)
    def delete(self, check_id: int, query: GroupQuery) -> Union[dict, tuple]:
        """
        Delete check
        ---
        tags:
        - 'SMTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to delete'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id, query)


class CheckRabbitView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'rabbitmq'

    @validate(query=GroupQuery)
    def get(self, check_id: int, query: GroupQuery) -> object:
        """
        Get RabbitMQ check or list of RabbitMQ checks, if without {check_id}.
        ---
        tags:
        - 'RabbitMQ Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'RabbitMQCheckDetails'
              properties:
                checks:
                  type: 'array'
                  description: 'List of checks inside multicheck'
                  items:
                    type: 'object'
                    properties:
                      interval:
                        type: 'integer'
                        description: 'Timeout interval'
                      ip:
                        type: 'string'
                        description: 'IP address to be tested'
                      port:
                        type: 'integer'
                        description: 'Port to be tested'
                      average_response_time:
                        type: 'integer'
                        description: 'Average response time in ms'
                      uptime:
                         type: 'integer'
                         description: 'Check uptime'
                      smon_id:
                        type: 'object'
                        description: 'RMON object'
                        properties:
                          check_timeout:
                            type: 'integer'
                            description: 'Check Timeout'
                          check_type:
                            type: 'string'
                            description: 'Check Type'
                          country_id:
                            type: 'integer'
                            description: 'Country ID'
                          created_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Creation Time'
                          description:
                            type: 'string'
                            description: 'Description'
                          enabled:
                            type: 'integer'
                            description: 'Enabled status'
                          check_group:
                            type: 'string'
                            description: 'Name of check group (optional)'
                          id:
                            type: 'integer'
                            description: 'ID'
                          mm_channel_id:
                            type: 'integer'
                            description: 'MM Channel ID'
                          email_channel_id:
                            type: 'integer'
                            description: 'Email channel ID (optional)'
                          multi_check_id:
                            type: 'integer'
                            description: 'Multi-check ID'
                          name:
                            type: 'string'
                            description: 'Name'
                          pd_channel_id:
                            type: 'integer'
                            description: 'PD Channel ID'
                          port:
                            type: 'integer'
                            description: 'Port'
                          region_id:
                            type: 'integer'
                            description: 'Region ID'
                          response_time:
                            type: 'string'
                            description: 'Response Time'
                          slack_channel_id:
                            type: 'integer'
                            description: 'Slack Channel ID'
                          status:
                            type: 'integer'
                            description: 'Status'
                          telegram_channel_id:
                            type: 'integer'
                            description: 'Telegram Channel ID'
                          time_state:
                            type: 'string'
                            format: 'date-time'
                            description: 'Time State'
                          updated_at:
                            type: 'string'
                            format: 'date-time'
                            description: 'Update Time'
                          group_id:
                            type: 'integer'
                            description: 'User Group'
                place:
                  type: 'string'
                  description: Where checks must be deployed
                  enum: ['all', 'country', 'region', 'agent']
                entities:
                  type: 'array'
                  description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                  items:
                    type: 'integer'
                ip:
                  type: 'string'
                  description: 'SMTP server to be tested'
                username:
                  type: 'string'
                  description: 'Username to connect to the RabbitMQ server'
                vhost:
                  type: 'string'
                  description: 'VHost to connect to the RabbitMQ server'
                interval:
                  type: 'integer'
                  description: 'Ping interval'
                ignore_ssl_error:
                  type: 'integer'
                  description: 'Ignore TLS/SSL error'
                retries:
                  type: 'integer'
                  description: 'Maximum retries before the service is marked as down and a notification is sent'
                  default: 3
                runbook:
                  type: 'string'
                  description: 'Link to runbook'
                priority:
                  type: 'string'
                  description: 'Alert priority'
                  default: 'critical'
                expiration:
                  type: 'string'
                  description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        """
        return super().get(check_id, query)

    @validate(body=RabbitCheckRequest)
    def post(self, body: RabbitCheckRequest) -> Union[dict, tuple]:
        """
        Create a new RabbitMQ check
        ---
        tags:
        - 'RabbitMQ Check'
        parameters:
        - in: 'body'
          name: 'body'
          description: 'RabbitMQ Check Details'
          required: true
          schema:
            id: 'CheckRabbitMQDetails'
            required:
              - name
              - ip
              - port
              - username
              - password
              - enabled
              - place
              - entities
            properties:
              name:
                type: 'string'
                description: 'Check name'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                type: 'array'
                description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                items:
                  type: 'integer'
              ip:
                type: 'string'
                description: 'IP address or domain name for RabbitMQ server check'
              port:
                type: 'integer'
                description: 'Port address or domain name for RabbitMQ server check'
                default: 5672
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              check_group:
                type: 'string'
                description: 'Name of check group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'integer'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              username:
                type: 'string'
                description: 'Username to connect to the RabbitMQ server'
              password:
                type: 'string'
                description: 'Password to connect to the RabbitMQ server'
              vhost:
                type: 'string'
                description: 'VHost to connect to the RabbitMQ server'
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              ignore_ssl_error:
                type: 'integer'
                description: 'Ignore TLS/SSL error'
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'CheckSMTPResponse'
              properties:
                id:
                  type: 'string'
                  description: 'ID of the created test case'
        """
        try:
            last_id = super().post(body)
            return IdResponse(status='Ok', id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, '')

    @validate(body=RabbitCheckRequest)
    def put(self, check_id: int, body: RabbitCheckRequest) -> Union[dict, tuple]:
        """
        Update RabbitMQ check
        ---
        tags:
        - 'RabbitMQ Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to update'
          required: true
          type: 'integer'
        - in: 'body'
          name: 'body'
          description: 'Object to be updated'
          required: true
          schema:
            id: 'SmonRabbitMQCheck'
            properties:
              name:
                type: 'string'
                description: 'Check name'
              place:
                type: 'string'
                description: Where checks must be deployed
                enum: ['all', 'country', 'region', 'agent']
              entities:
                 type: 'array'
                 description: List of agents, regions, or countries. What exactly will be chosen depends on the place parameter
                 items:
                   type: 'integer'
              ip:
                type: 'string'
                description: 'IP address or domain of RabbitMQ server check'
              port:
                type: 'integer'
                description: 'Port address or domain name for RabbitMQ server check'
                default: 5672
              enabled:
                type: 'integer'
                description: 'Enable status (1 for enabled)'
              group:
                type: 'string'
                description: 'Group (optional)'
              description:
                type: 'string'
                description: 'Description (optional)'
              telegram_channel_id:
                type: 'integer'
                description: 'Telegram channel ID (optional)'
              slack_channel_id:
                type: 'integer'
                description: 'Slack channel ID (optional)'
              pd_channel_id:
                type: 'integer'
                description: 'Pager Duty channel ID (optional)'
              mm_channel_id:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              email_channel_id:
                type: 'integer'
                description: 'Email channel ID (optional)'
              username:
                type: 'string'
                description: 'Username to connect to the RabbitMQ server'
              password:
                type: 'string'
                description: 'Password to connect to the RabbitMQ server'
              vhost:
                type: 'string'
                description: 'VHost to connect to the RabbitMQ server'
              interval:
                type: 'integer'
                description: 'Interval check (optional)'
                default: 120
              region_id:
                type: 'integer'
                description: 'Region ID'
              check_timeout:
                type: 'integer'
                description: 'Timeout (optional)'
                default: 2
              ignore_ssl_error:
                type: 'integer'
                description: 'Ignore TLS/SSL error'
              retries:
                type: 'integer'
                description: 'Maximum retries before the service is marked as down and a notification is sent'
                default: 3
              runbook:
                type: 'string'
                description: 'Link to runbook'
              priority:
                type: 'string'
                description: Where checks must be deployed
                enum: ['info', 'warning', 'error', 'critical']
              expiration:
                type: 'string'
                description: 'Expiration date. After this date, the check will be disabled. Format: YYYY-MM-DD HH:MM:SS. Must be in UTC time.'
        responses:
          '201':
            description: 'Successful Operation, Ping Check updated'
          '404':
            description: 'Ping Check not found'
        """
        try:
            super().put(check_id, body)
            return BaseResponse(status='Ok').model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot update {self.check_type} check')

    @validate(query=GroupQuery)
    def delete(self, check_id: int, query: GroupQuery) -> Union[dict, tuple]:
        """
        Delete check
        ---
        tags:
        - 'RabbitMQ Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to delete'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id, query)
