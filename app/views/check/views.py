from typing import Union

from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import g, abort
from flask_pydantic import validate
from playhouse.shortcuts import model_to_dict

import app.modules.db.smon as smon_sql
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.smon as smon_mod
from app.middleware import get_user_params, check_group
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.db.db_model import SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck
from app.modules.roxywi.class_models import IdResponse, HttpCheckRequest, DnsCheckRequest, TcpCheckRequest, PingCheckRequest, BaseResponse


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
        self.group_id = g.user_params['group_id']
        self.check_type = None
        self.create_func = {
            'http': smon_mod.create_http_check,
            'tcp': smon_mod.create_tcp_check,
            'dns': smon_mod.create_dns_check,
            'ping': smon_mod.create_ping_check
        }

    def get(self, check_id: int) -> Union[SmonTcpCheck, SmonHttpCheck, SmonDnsCheck, SmonPingCheck]:
        if check_id:
            check_type_id = smon_mod.get_check_id_by_name(self.check_type)
            checks = smon_sql.select_one_smon(check_id, check_type_id=check_type_id)
            for check in checks:
                return model_to_dict(check)
            else:
                abort(404, f'{self.check_type} check not found')
        else:
            checks = smon_sql.select_smon_checks(self.check_type, self.group_id)
            check_list = []
            for check in checks:
                check_list.append(model_to_dict(check))
            return check_list

    def post(self, data) -> int:
        """
        post(self, data) -> Union[int, tuple]:

        This method is responsible for handling a POST request with the provided data.

        Parameters:
        - data: The data to be processed.

        Returns:
        - int: The last ID of the created check if successful.
        - tuple: An exception message and an empty string if an error occurs during the process.

        Note:
        - This method internally calls 'check_checks_limit()' and 'create_check()' methods from 'smon_mod' module.
        - If any exception occurs during the process, the 'handler_exceptions_for_json_data' function from 'roxywi_common' module is used to handle and return the exception message.
        - In case of success, the last ID of the created check is returned.
        - If an error occurs, a tuple with the exception message and an error message specific to the check type is returned.
        """
        try:
            smon_mod.check_checks_limit()
        except Exception as e:
            raise e

        try:
            last_id = smon_mod.create_check(data, self.group_id, self.check_type)
        except Exception as e:
            raise e

        try:
            smon_mod.create_http_check(data, last_id)
            smon_mod.send_new_check(last_id, data)
        except Exception as e:
            raise e

        return last_id

    def put(self, check_id: int, data) -> None:
        try:
            smon_mod.update_smon(check_id, data, self.group_id)
        except Exception as e:
            raise e
        try:
            self.create_func[self.check_type](data, check_id)
            if data.enabled:
                smon_mod.send_new_check(check_id, data)
        except Exception as e:
            raise e

    def delete(self, check_id: int) -> Union[int, tuple]:
        try:
            smon_mod.delete_smon(check_id, self.group_id)
            return BaseResponse(status='Ok').model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, f'Cannot delete {self.check_type} check')


class CheckHttpView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'http'

    def get(self, check_id: int) -> SmonHttpCheck:
        """
        Get HTTP check or list of HTTP checks, if without {check_id}.
        ---
        tags:
        - 'HTTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve'
          required: true
          schema:
            type: 'integer'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'HttpCheck'
              properties:
                smon_id:
                  type: 'object'
                  description: 'SMON object'
                  properties:
                    id:
                      type: 'integer'
                      description: 'SMON ID'
                    name:
                      type: 'string'
                      description: 'Name'
                    port:
                      type: 'integer'
                      description: 'Port'
                    status:
                      type: 'integer'
                      description: 'Status'
                    en:
                      type: 'integer'
                      description: 'EN'
                    desc:
                      type: 'string'
                      description: 'Description'
                    time_state:
                      type: 'string'
                      format: 'date-time'
                      description: 'Time State'
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
                agent_id:
                  type: 'integer'
                  description: 'Agent ID'
                headers:
                  type: 'string'
                  description: 'Headers'
                body_req:
                  type: 'string'
                  description: 'Body Request'
        """
        return super().get(check_id)

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
              - ip
              - enabled
              - url
              - http_method
              - agent_id
            properties:
              name:
                type: 'string'
                description: 'Check name'
              enabled:
                type: 'string'
                description: 'Enable status (1 for enabled)'
              url:
                type: 'string'
                description: 'URL to be tested'
              body:
                type: 'string'
                description: 'Body content (optional)'
              group:
                type: 'string'
                description: 'Group (optional)'
              desc:
                type: 'string'
                description: 'Description (optional)'
              tg:
                type: 'string'
                description: 'Telegram channel ID (optional)'
              slack:
                type: 'string'
                description: 'Slack channel ID (optional)'
              pd:
                type: 'string'
                description: 'Pager Duty channel ID (optional)'
              mm:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              http_method:
                  type: 'string'
                  description: 'HTTP method'
                  enum: ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
              interval:
                type: 'string'
                description: 'Interval check (optional)'
                default: 120
              agent_id:
                type: 'string'
                description: 'Agent ID'
              body_req:
                type: 'string'
                description: 'Body Request (optional)'
              header_req:
                type: 'string'
                description: 'Header Request (optional)'
              accepted_status_codes:
                type: 'string'
                description: 'Expected status code (default to 200, optional)'
                minimum: 100
                maximum: 599
              timeout:
                type: 'string'
                description: 'Timeout (optional)'
                default: 2
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
          schema:
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
                type: 'string'
                description: 'Enable status (1 for enabled)'
              url:
                type: 'string'
                description: 'URL to be tested'
              body:
                type: 'string'
                description: 'Body content (optional)'
              group:
                type: 'string'
                description: 'Group (optional)'
              desc:
                type: 'string'
                description: 'Description (optional)'
              tg:
                type: 'string'
                description: 'Telegram channel ID (optional)'
              slack:
                type: 'string'
                description: 'Slack channel ID (optional)'
              pd:
                type: 'string'
                description: 'Pager Duty channel ID (optional)'
              mm:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              http_method:
                  type: 'string'
                  description: 'HTTP method'
                  enum: ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
              interval:
                type: 'string'
                description: 'Interval check (optional)'
                default: 120
              agent_id:
                type: 'string'
                description: 'Agent ID'
              body_req:
                type: 'string'
                description: 'Body Request (optional)'
              header_req:
                type: 'string'
                description: 'Header Request (optional)'
              accepted_status_codes:
                type: 'string'
                description: 'Expected status code (default to 200, optional)'
                minimum: 100
                maximum: 599
              timeout:
                type: 'string'
                description: 'Timeout (optional)'
                default: 2
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

    @validate()
    def delete(self, check_id: int) -> Union[dict, tuple]:
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
          schema:
            type: 'integer'
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id)


class CheckTcpView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'tcp'

    def get(self, check_id: int) -> SmonTcpCheck:
        """
        Get TCP check or list of TCP checks, if without {check_id}.
        ---
        tags:
        - 'TCP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve'
          required: true
          schema:
            type: 'integer'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'SmonTcpCheck'
              properties:
                smon_id:
                  type: 'object'
                  description: 'SMON object'
                  properties:
                    id:
                      type: 'integer'
                      description: 'SMON ID'
                    name:
                      type: 'string'
                      description: 'Name'
                    port:
                      type: 'integer'
                      description: 'Port'
                    status:
                      type: 'integer'
                      description: 'Status'
                    en:
                      type: 'integer'
                      description: 'EN'
                    desc:
                      type: 'string'
                      description: 'Description'
                    time_state:
                      type: 'string'
                      format: 'date-time'
                      description: 'Time State'
                ip:
                  type: 'string'
                  description: 'IP address to be tested'
                port:
                  type: 'integer'
                  description: 'Port to be tested'
                interval:
                  type: 'integer'
                  description: 'Check interval'
                agent_id:
                  type: 'integer'
                  description: 'Agent ID'
        """
        return super().get(check_id)

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
              - agent_id
            properties:
              name:
                type: 'string'
                description: 'Name of the test tcp'
              ip:
                type: 'string'
                description: 'IP address or domain name for the TCP check'
              port:
                type: 'string'
                description: 'Port number'
                minimum: 1
                maximum: 65535
              enabled:
                type: 'string'
                description: 'Enable status (1 for enabled)'
              group:
                type: 'string'
                description: 'Group (optional)'
              desc:
                type: 'string'
                description: 'Description (optional)'
              tg:
                type: 'string'
                description: 'Telegram channel ID (optional)'
              slack:
                type: 'string'
                description: 'Slack channel ID (optional)'
              pd:
                type: 'string'
                description: 'Pager Duty channel ID (optional)'
              mm:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              interval:
                type: 'string'
                description: 'Interval check (default to 120, optional)'
              agent_id:
                type: 'string'
                description: 'Agent ID'
              timeout:
                type: 'string'
                description: 'Timeout (optional)'
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
          schema:
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
                type: 'string'
                description: 'Port number'
                minimum: 1
                maximum: 65535
              enabled:
                type: 'string'
                description: 'Enable status (1 for enabled)'
              group:
                type: 'string'
                description: 'Group (optional)'
              desc:
                type: 'string'
                description: 'Description (optional)'
              tg:
                type: 'string'
                description: 'Telegram channel ID (optional)'
              slack:
                type: 'string'
                description: 'Slack channel ID (optional)'
              pd:
                type: 'string'
                description: 'Pager Duty channel ID (optional)'
              mm:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              interval:
                type: 'string'
                description: 'Interval check (default to 120, optional)'
              agent_id:
                type: 'string'
                description: 'Agent ID'
              timeout:
                type: 'string'
                description: 'Timeout (optional)'
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

    @validate()
    def delete(self, check_id: int) -> Union[dict, tuple]:
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
          schema:
            type: 'integer'
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id)


class CheckDnsView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'dns'

    def get(self, check_id: int) -> SmonDnsCheck:
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
          schema:
            type: 'integer'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'SmonDnsCheck'
              properties:
                smon_id:
                  type: 'object'
                  description: 'SMON object'
                  properties:
                    id:
                      type: 'integer'
                      description: 'SMON ID'
                    name:
                      type: 'string'
                      description: 'Name'
                    port:
                      type: 'integer'
                      description: 'Port'
                    status:
                      type: 'integer'
                      description: 'Status'
                    en:
                      type: 'integer'
                      description: 'EN'
                    desc:
                      type: 'string'
                      description: 'Description'
                    time_state:
                      type: 'string'
                      format: 'date-time'
                      description: 'Time State'
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
                agent_id:
                  type: 'integer'
                  description: 'Agent ID'
        """
        return super().get(check_id)

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
              - agent_id
            properties:
              name:
                type: 'string'
                description: 'Name of the test dns'
              ip:
                type: 'string'
                description: 'Resolver IP address or domain name'
              port:
                type: 'string'
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
                type: 'string'
                description: 'Enable status (1 for enabled)'
              group:
                type: 'string'
                description: 'Group (optional)'
              desc:
                type: 'string'
                description: 'Description (optional)'
              tg:
                type: 'string'
                description: 'Telegram channel ID (optional)'
              slack:
                type: 'string'
                description: 'Slack channel ID (optional)'
              pd:
                type: 'string'
                description: 'Pager Duty channel ID (optional)'
              mm:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              interval:
                type: 'string'
                description: 'Interval check (optional)'
                default: 120
              agent_id:
                type: 'string'
                description: 'Agent ID'
              timeout:
                type: 'string'
                description: 'Timeout (optional)'
                default: 2
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
          schema:
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
              ip:
                type: 'string'
                description: 'Resolver IP address or domain name'
              port:
                type: 'string'
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
                type: 'string'
                description: 'Enable status (1 for enabled)'
              group:
                type: 'string'
                description: 'Group (optional)'
              desc:
                type: 'string'
                description: 'Description (optional)'
              tg:
                type: 'string'
                description: 'Telegram channel ID (optional)'
              slack:
                type: 'string'
                description: 'Slack channel ID (optional)'
              pd:
                type: 'string'
                description: 'Pager Duty channel ID (optional)'
              mm:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              interval:
                type: 'string'
                description: 'Interval check (optional)'
                default: 120
              agent_id:
                type: 'string'
                description: 'Agent ID'
              timeout:
                type: 'string'
                description: 'Timeout (optional)'
                default: 2
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

    @validate()
    def delete(self, check_id: int) -> Union[dict, tuple]:
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
          schema:
            type: 'integer'
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id)


class CheckPingView(CheckView):
    def __init__(self):
        super().__init__()
        self.check_type = 'ping'

    def get(self, check_id: int) -> SmonPingCheck:
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
          schema:
            type: 'integer'
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'PingCheckDetails'
              properties:
                smon_id:
                  type: 'object'
                  description: 'SMON object'
                  properties:
                    id:
                      type: 'integer'
                      description: 'SMON ID'
                    name:
                      type: 'string'
                      description: 'Name'
                    port:
                      type: 'integer'
                      description: 'Port'
                    status:
                      type: 'integer'
                      description: 'Status'
                    en:
                      type: 'integer'
                      description: 'EN'
                    desc:
                      type: 'string'
                      description: 'Description'
                    time_state:
                      type: 'string'
                      format: 'date-time'
                      description: 'Time State'
                ip:
                  type: 'string'
                  description: 'IP address to be tested'
                packet_size:
                  type: 'integer'
                  description: 'Size of the packet to be sent'
                interval:
                  type: 'integer'
                  description: 'Ping interval'
                agent_id:
                  type: 'integer'
                  description: 'Agent ID'
        """
        return super().get(check_id)

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
              - agent_id
            properties:
              name:
                type: 'string'
                description: 'Check name'
              ip:
                type: 'string'
                description: 'IP address or domain name for Ping check'
              enabled:
                type: 'string'
                description: 'Enable status (1 for enabled)'
              group:
                type: 'string'
                description: 'Group (optional)'
              desc:
                type: 'string'
                description: 'Description (optional)'
              tg:
                type: 'string'
                description: 'Telegram channel ID (optional)'
              slack:
                type: 'string'
                description: 'Slack channel ID (optional)'
              pd:
                type: 'string'
                description: 'Pager Duty channel ID (optional)'
              mm:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              packet_size:
                type: 'string'
                description: 'Packet size (optional)'
                default: 56
              interval:
                type: 'string'
                description: 'Interval check (optional)'
                default: 120
              agent_id:
                type: 'string'
                description: 'Agent ID'
              timeout:
                type: 'string'
                description: 'Timeout (optional)'
                default: 2
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'CheckPingResponse'
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
          schema:
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
              ip:
                type: 'string'
                description: 'IP address or domain name for Ping check'
              enabled:
                type: 'string'
                description: 'Enable status (1 for enabled)'
              group:
                type: 'string'
                description: 'Group (optional)'
              desc:
                type: 'string'
                description: 'Description (optional)'
              tg:
                type: 'string'
                description: 'Telegram channel ID (optional)'
              slack:
                type: 'string'
                description: 'Slack channel ID (optional)'
              pd:
                type: 'string'
                description: 'Pager Duty channel ID (optional)'
              mm:
                type: 'string'
                description: 'Mattermost channel ID (optional)'
              packet_size:
                type: 'string'
                description: 'Packet size (optional)'
                default: 56
              interval:
                type: 'string'
                description: 'Interval check (optional)'
                default: 120
              agent_id:
                type: 'string'
                description: 'Agent ID'
              timeout:
                type: 'string'
                description: 'Timeout (optional)'
                default: 2
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

    @validate()
    def delete(self, check_id: int) -> Union[dict, tuple]:
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
          schema:
            type: 'integer'
        responses:
          '204':
            description: 'Successful Deletion'
          '404':
            description: 'Check Not Found'
        """
        return super().delete(check_id)
