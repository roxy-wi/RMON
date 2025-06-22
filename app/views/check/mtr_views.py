import json

from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify

import app.modules.db.smon as smon_sql
import app.modules.tools.smon as smon_mod
import app.modules.server.server as server_mod
from app.middleware import get_user_params, check_group


class MtrCheckView(MethodView):
    methods = ['GET']
    decorators = [jwt_required(), get_user_params(), check_group()]

    def get(self, check_id: int):
        """
        Get route report for check
        ---
        tags:
          - 'Check route report'
        parameters:
          - in: path
            name: check_id
            description: ID of the check to retrieve MTR report
            required: true
            type: integer
        responses:
          200:
            description: Successful retrieval of MTR report
            schema:
              type: object
              properties:
                report:
                  type: object
                  properties:
                    hubs:
                      type: array
                      items:
                        type: object
                        properties:
                          Avg:
                            type: number
                            description: Average round-trip time
                            example: 8.965
                          Best:
                            type: number
                            description: Best round-trip time
                            example: 8.965
                          Last:
                            type: number
                            description: Last round-trip time
                            example: 8.965
                          Loss%:
                            type: number
                            description: Packet loss percentage
                            example: 0
                          Snt:
                            type: integer
                            description: Number of packets sent
                            example: 1
                          StDev:
                            type: number
                            description: Standard deviation of round-trip times
                            example: 0
                          Wrst:
                            type: number
                            description: Worst round-trip time
                            example: 8.965
                          count:
                            type: integer
                            description: Hub count in trace route
                            example: 1
                          host:
                            type: string
                            description: IP address or hostname of the hub
                            example: "10.92.71.254"
          404:
            description: Check not found
          400:
            description: Invalid request parameters
        """

        smon = smon_sql.get_smon(check_id)
        server_ip = smon_sql.select_server_ip_by_agent_id(smon.agent_id)
        check_type_id = smon_mod.get_check_id_by_name(smon.check_type)
        check = smon_sql.select_one_smon(check_id, check_type_id)
        for c in check:
            if smon.check_type == 'http':
                ip = c.url.split('//')[1].split('/')[0]
                remote_host = ip
            else:
                remote_host = c.ip
            break
        cmd = f'mtr -j -c 1 -m 15 -G 5 {remote_host}'
        output = server_mod.ssh_command(server_ip, cmd, timeout=20)
        json_output = json.loads(output)
        try:
            del json_output['report']['mtr']
        except Exception:
            pass
        return jsonify(json_output)
