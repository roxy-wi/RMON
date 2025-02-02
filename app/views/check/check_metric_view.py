from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify
from flask_pydantic import validate

import app.modules.db.sql as sql
import app.modules.db.smon as smon_sql
import app.modules.tools.smon as smon_mod
import app.modules.common.common as common
import app.modules.roxywi.common as roxywi_common
from app.modules.common.common_classes import SupportClass
from app.middleware import get_user_params, check_group
from app.modules.roxywi.class_models import CheckMetricsQuery


class ChecksMetricView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    def __init__(self):
        self.check_type = None
        self.check_type_id = None

    def get(self, check_id: int, query: CheckMetricsQuery):
        group_id = SupportClass.return_group_id(query)
        is_vm = sql.get_setting('use_victoria_metrics')

        try:
            smon_sql.select_check_with_group(check_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot find the check')

        if is_vm:
            try:
                return jsonify(smon_mod.history_metrics_from_vm(check_id, query))
            except Exception as e:
                return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get metrics')
        else:
            return jsonify(smon_mod.history_metrics(check_id, self.check_type_id))


class ChecksMetricViewHttp(ChecksMetricView):
    def __init__(self):
        super().__init__()
        self.check_type = 'http'
        self.check_type_id = 2

    @validate(query=CheckMetricsQuery)
    def get(self, check_id: int, query: CheckMetricsQuery):
        """
        Get HTTP metrics check.
        ---
        tags:
        - 'HTTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve metrics for'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        - name: step
          in: query
          description: The interval between data points, which must be returned from the range query. Only if VictoriaMetrics is used.
          default: 30s
          type: string
        - name: start
          in: query
          description: The starting timestamp of the time range for query evaluation. Only if VictoriaMetrics is used.
          default: now - 30m
          type: string
        - name: end
          in: query
          description: the ending timestamp of the time range for query evaluation. If the end isn’t set, then the end is automatically set to the current time. Only if VictoriaMetrics is used.
          default: now
          type: string
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'HttpMetricsCheck'
              properties:
                chartData:
                  type: 'object'
                  description: 'HTTP metrics for the check'
                  properties:
                    appconnect:
                      type: 'string'
                      description: 'App connect times, comma-separated'
                    connect:
                      type: 'string'
                      description: 'Connect times, comma-separated'
                    response_time:
                      type: 'string'
                      description: 'Current connections, comma-separated'
                    download:
                      type: 'string'
                      description: 'Download times, comma-separated'
                    labels:
                      type: 'string'
                      description: 'Time labels, comma-separated'
                    namelookup:
                      type: 'string'
                      description: 'Name lookup times, comma-separated'
                    pretransfer:
                      type: 'string'
                      description: 'Pre-transfer times, comma-separated'
                    redirect:
                      type: 'string'
                      description: 'Redirect times, comma-separated'
                    starttransfer:
                      type: 'string'
                      description: 'Start transfer times, comma-separated'
        """
        return super().get(check_id, query)


class ChecksMetricViewTcp(ChecksMetricView):
    def __init__(self):
        super().__init__()
        self.check_type = 'tcp'
        self.check_type_id = 1

    @validate(query=CheckMetricsQuery)
    def get(self, check_id: int, query: CheckMetricsQuery):
        """
        Get TCP metrics check.
        ---
        tags:
        - 'TCP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve metrics for'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        - name: step
          in: query
          description: The interval between data points, which must be returned from the range query. Only if VictoriaMetrics is used.
          default: 30s
          type: string
        - name: start
          in: query
          description: The starting timestamp of the time range for query evaluation. Only if VictoriaMetrics is used.
          default: now - 30m
          type: string
        - name: end
          in: query
          description: the ending timestamp of the time range for query evaluation. If the end isn’t set, then the end is automatically set to the current time. Only if VictoriaMetrics is used.
          default: now
          type: string
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'TCPMetricsCheck'
              properties:
                chartData:
                  type: 'object'
                  description: 'TCP metrics for the check'
                  properties:
                    response_time:
                      type: 'string'
                      description: 'Current connections, comma-separated'
                    labels:
                      type: 'string'
                      description: 'Time labels, comma-separated'
        """
        return super().get(check_id, query)


class ChecksMetricViewSMTP(ChecksMetricView):
    def __init__(self):
        super().__init__()
        self.check_type = 'smtp'
        self.check_type_id = 3

    @validate(query=CheckMetricsQuery)
    def get(self, check_id: int, query: CheckMetricsQuery):
        """
        Get SMTP metrics check.
        ---
        tags:
        - 'SMTP Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve metrics for'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        - name: step
          in: query
          description: The interval between data points, which must be returned from the range query. Only if VictoriaMetrics is used.
          default: 30s
          type: string
        - name: start
          in: query
          description: The starting timestamp of the time range for query evaluation. Only if VictoriaMetrics is used.
          default: now - 30m
          type: string
        - name: end
          in: query
          description: the ending timestamp of the time range for query evaluation. If the end isn’t set, then the end is automatically set to the current time. Only if VictoriaMetrics is used.
          default: now
          type: string
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'SMTPMetricsCheck'
              properties:
                chartData:
                  type: 'object'
                  description: 'SMTP metrics for the check'
                  properties:
                    appconnect:
                      type: 'string'
                      description: 'App connect times, comma-separated'
                    connect:
                      type: 'string'
                      description: 'Connect times, comma-separated'
                    response_time:
                      type: 'string'
                      description: 'Current connections, comma-separated'
                    download:
                      type: 'string'
                      description: 'Download times, comma-separated'
                    labels:
                      type: 'string'
                      description: 'Time labels, comma-separated'
                    namelookup:
                      type: 'string'
                      description: 'Name lookup times, comma-separated'
        """
        return super().get(check_id, query)


class ChecksMetricViewPing(ChecksMetricView):
    def __init__(self):
        super().__init__()
        self.check_type = 'ping'
        self.check_type_id = 4

    @validate(query=CheckMetricsQuery)
    def get(self, check_id: int, query: CheckMetricsQuery):
        """
        Get Ping metrics check.
        ---
        tags:
        - 'Ping Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve metrics for'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        - name: step
          in: query
          description: The interval between data points, which must be returned from the range query. Only if VictoriaMetrics is used.
          default: 30s
          type: string
        - name: start
          in: query
          description: The starting timestamp of the time range for query evaluation. Only if VictoriaMetrics is used.
          default: now - 30m
          type: string
        - name: end
          in: query
          description: the ending timestamp of the time range for query evaluation. If the end isn’t set, then the end is automatically set to the current time. Only if VictoriaMetrics is used.
          default: now
          type: string
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'PingMetricsCheck'
              properties:
                chartData:
                  type: 'object'
                  description: 'Ping metrics for the check'
                  properties:
                    response_time:
                      type: 'string'
                      description: 'Current connections, comma-separated'
                    labels:
                      type: 'string'
                      description: 'Time labels, comma-separated'
        """
        return super().get(check_id, query)


class ChecksMetricViewDNS(ChecksMetricView):
    def __init__(self):
        super().__init__()
        self.check_type = 'ping'
        self.check_type_id = 5

    @validate(query=CheckMetricsQuery)
    def get(self, check_id: int, query: CheckMetricsQuery):
        """
        Get DNS metrics check.
        ---
        tags:
        - 'DNS Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve metrics for'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        - name: step
          in: query
          description: The interval between data points, which must be returned from the range query. Only if VictoriaMetrics is used.
          default: 30s
          type: string
        - name: start
          in: query
          description: The starting timestamp of the time range for query evaluation. Only if VictoriaMetrics is used.
          default: now - 30m
          type: string
        - name: end
          in: query
          description: the ending timestamp of the time range for query evaluation. If the end isn’t set, then the end is automatically set to the current time. Only if VictoriaMetrics is used.
          default: now
          type: string
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'DNSMetricsCheck'
              properties:
                chartData:
                  type: 'object'
                  description: 'DNS metrics for the check'
                  properties:
                    response_time:
                      type: 'string'
                      description: 'Current connections, comma-separated'
                    labels:
                      type: 'string'
                      description: 'Time labels, comma-separated'
        """
        return super().get(check_id, query)


class ChecksMetricViewRabbitmq(ChecksMetricView):
    def __init__(self):
        super().__init__()
        self.check_type = 'rabbitmq'
        self.check_type_id = 6

    @validate(query=CheckMetricsQuery)
    def get(self, check_id: int, query: CheckMetricsQuery):
        """
        Get RabbitMQ metrics check.
        ---
        tags:
        - 'RabbitMQ Check'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve metrics for'
          required: true
          type: 'integer'
        - name: group_id
          in: query
          description: This parameter is used only for the superAdmin role.
          required: false
          type: integer
        - name: step
          in: query
          description: The interval between data points, which must be returned from the range query. Only if VictoriaMetrics is used.
          default: 30s
          type: string
        - name: start
          in: query
          description: The starting timestamp of the time range for query evaluation. Only if VictoriaMetrics is used.
          default: now - 30m
          type: string
        - name: end
          in: query
          description: the ending timestamp of the time range for query evaluation. If the end isn’t set, then the end is automatically set to the current time. Only if VictoriaMetrics is used.
          default: now
          type: string
        responses:
          '200':
            description: 'Successful Operation'
            schema:
              id: 'RabbitMQMetricsCheck'
              properties:
                chartData:
                  type: 'object'
                  description: 'RabbitMQ metrics for the check'
                  properties:
                    response_time:
                      type: 'string'
                      description: 'Current connections, comma-separated'
                    labels:
                      type: 'string'
                      description: 'Time labels, comma-separated'
        """
        return super().get(check_id, query)


class CheckStatusesView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=CheckMetricsQuery)
    def get(self, check_id: int, query: CheckMetricsQuery):
        """
        Get Check Statuses.
        ---
        tags:
        - 'Check Statuses'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve statuses for'
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
              type: 'array'
              items:
                type: 'object'
                properties:
                  date:
                    type: 'string'
                    format: 'date-time'
                    description: 'Date and time of the status'
                  error:
                    type: 'string'
                    description: 'Error message, if any'
                  status:
                    type: 'integer'
                    description: 'Status value'
        """
        group_id = SupportClass.return_group_id(query)

        try:
            smon_sql.select_check_with_group(check_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find the check')

        try:
            statuses = smon_sql.select_smon_history(check_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get statuses')

        return jsonify(
            [{'status': s.status, 'date': common.get_time_zoned_date(s.date), 'error': s.mes} for s in statuses]
        )


class CheckStatusView(MethodView):
    methods = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=CheckMetricsQuery)
    def get(self, check_id: int, query: CheckMetricsQuery):
        """
        Get Check current Status.
        ---
        tags:
        - 'Check Statuses'
        parameters:
        - in: 'path'
          name: 'check_id'
          description: 'ID of the check to retrieve status for'
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
              properties:
                status:
                  type: 'integer'
                  description: 'Current status of check: 1 - up, 0 - down'
        """
        group_id = SupportClass.return_group_id(query)

        try:
            smon_sql.select_check_with_group(check_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find the check')

        try:
            status = smon_sql.get_history(check_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get statuses')

        return jsonify({'status': status.status})
