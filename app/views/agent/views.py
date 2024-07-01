from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import render_template, jsonify, request, g
from playhouse.shortcuts import model_to_dict
from flask_pydantic import validate

import app.modules.db.smon as smon_sql
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.common as tools_common
import app.modules.tools.smon_agent as smon_agent
from app.middleware import get_user_params, check_group
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.roxywi.class_models import BaseResponse, IdResponse, RmonAgent


class AgentView(MethodView):
    method_decorators = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    def __init__(self):
        """
        Initialize AgentView instance
        ---
        parameters:
          - name: is_api
            in: path
            type: boolean
            description: is api
        """
        self.json_data = request.get_json()

    def get(self, agent_id: int):
        """
        Get an agent
        ---
        tags:
          - Agent
        responses:
          200:
            description: Information about an agent
            schema:
              type: array
              items:
                id: Agent
                properties:
                  desc:
                    type: string
                    description: A brief description of the Agent
                    example: Agent description
                  enabled:
                    type: integer
                    description: Indicates whether the Agent is enabled or not
                    example: 0
                  id:
                    type: integer
                    description: The ID for the Agent
                    example: 1
                  name:
                    type: string
                    description: Name for the Agent
                    example: Agent name
                  port:
                    type: integer
                    description: The Agent's port
                    example: 5102
                  server_id:
                    type: object
                    properties:
                      alert:
                        type: integer
                        example: 0
                      cred:
                        type: integer
                        example: 1
                      desc:
                        type: string
                        example: ""
                      enable:
                        type: integer
                        example: 1
                      group_id:
                        type: string
                        example: "1"
                      hostname:
                        type: string
                        example: "localhost"
                      ip:
                        type: string
                        example: "127.0.0.1"
                      port:
                        type: integer
                        example: 22
                      pos:
                        type: integer
                        example: 0
                      server_id:
                        type: integer
                        example: 1
                  shared:
                    type: integer
                    description: Indicates whether the Agent is shared or not
                    example: 0
                  uuid:
                    type: string
                    description: A unique identifier for the Agent
                    format: uuid
                    example: cf2cc8d2-4c44-48d1-9ed3-f6f49f8327fa
        """
        try:
            group = int(g.user_params['group_id'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse agent data')
        try:
            agents = smon_sql.get_agent_with_group(agent_id, group)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get agent')
        agent_list = []
        for agent in agents:
            agent_dict = model_to_dict(agent)
            agent_list.append(agent_dict)
        try:
            if len(agent_list) == 0:
                raise RoxywiResourceNotFound
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, '')
        return jsonify(agent_list)

    @validate(body=RmonAgent)
    def post(self, body: RmonAgent):
        """
        Creates a new agent
        ---
        tags:
          - Agent
        parameters:
          - in: body
            name: body
            schema:
              id: AgentCreate
              required:
                - name
                - server_id
                - port
                - desc
                - enabled
                - shared
                - reconfigure
              properties:
                name:
                  type: string
                  description: Name for the Agent
                  example: Agent name
                server_id:
                  type: string
                  description: The server ID for the Agent
                  example: 1
                port:
                  type: string
                  description: The Agent's port
                  example: 5102
                desc:
                  type: string
                  description: A brief description of the Agent
                  example: Agent description
                enabled:
                  type: integer
                  description: Indicates whether the Agent is enabled or not
                  example: 0
                shared:
                  type: integer
                  description: Indicates whether the Agent is shared or not
                  example: 0
                reconfigure:
                  type: string
                  description: If 1 agent will be reconfigured
                  example: 1
        responses:
          201:
            description: Agent successfully created
            schema:
              id: AgentCreated
              properties:
                id:
                  type: string
                  description: The ID of the created Agent
          400:
            description: Invalid payload received
        """
        try:
            last_id = smon_agent.add_agent(body)
            return IdResponse(id=last_id).model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot add agent')

    @validate(body=RmonAgent)
    def put(self, agent_id: int, body: RmonAgent):
        """
        Updates an agent
        ---
        tags:
          - Agent
        parameters:
          - in: 'path'
            name: 'agent_id'
            description: 'ID of the agent to update'
            required: true
            schema:
              type: 'integer'
          - in: body
            name: body
            schema:
              id: AgentUpdate
              required:
                - name
                - server_id
                - port
                - desc
                - enabled
                - shared
                - agent_id
                - reconfigure
              properties:
                name:
                  type: string
                  description: Name for the Agent
                  example: Agent name
                server_id:
                  type: string
                  description: The server ID for the Agent
                  example: 1
                port:
                  type: string
                  description: The Agent's port
                  example: 5102
                desc:
                  type: string
                  description: A brief description of the Agent
                  example: Agent description
                enabled:
                  type: integer
                  description: Indicates whether the Agent is enabled or not
                  example: 0
                shared:
                  type: integer
                  description: Indicates whether the Agent is shared or not
                  example: 0
                agent_id:
                  type: string
                  description: A unique identifier for the Agent
                  example: 1
                reconfigure:
                  type: string
                  description: If 1 agent will be reconfigured
                  example: 1
        responses:
          201:
            description: Agent successfully updated
          400:
            description: Invalid payload received
        """
        try:
            smon_agent.update_agent(agent_id, body)
            return BaseResponse().model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot update agent')

    def delete(self):
        """
        Remove a specific agent.
        ---
        tags:
          - Agent
        parameters:
          - in: 'path'
            name: 'agent_id'
            description: 'ID of the agent to remove'
            required: true
            schema:
              type: 'integer'
        responses:
          200:
            description: Agent successfully deleted
          400:
            description: Invalid ID supplied
          404:
            description: Agent not found
        """
        try:
            agent_id = int(self.json_data('agent_id'))
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot parse server data')
        try:
            _ = smon_sql.get_agent_uuid(agent_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get agent uuid')

        try:
            smon_agent.delete_agent(agent_id)
            smon_sql.delete_agent(agent_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot delete agent')


class AgentsView(MethodView):
    method_decorators = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    def __init__(self, is_api=False):
        """
        Initialize AgentView instance
        ---
        parameters:
          - name: is_api
            in: path
            type: boolean
            description: is api
        """
        self.json_data = request.get_json()
        self.is_api = is_api

    def get(self):
        """
        Get a list of all RMON agents.
        ---
        tags:
          - Agent
        responses:
          200:
            description: A list of agents
            schema:
              type: array
              items:
                id: Agent
                properties:
                  desc:
                    type: string
                    description: A brief description of the Agent
                    example: Agent description
                  enabled:
                    type: integer
                    description: Indicates whether the Agent is enabled or not
                    example: 0
                  id:
                    type: integer
                    description: The ID for the Agent
                    example: 1
                  name:
                    type: string
                    description: Name for the Agent
                    example: Agent name
                  port:
                    type: integer
                    description: The Agent's port
                    example: 5102
                  server_id:
                    type: object
                    properties:
                      alert:
                        type: integer
                        example: 0
                      cred:
                        type: integer
                        example: 1
                      desc:
                        type: string
                        example: ""
                      enable:
                        type: integer
                        example: 1
                      group_id:
                        type: string
                        example: "1"
                      hostname:
                        type: string
                        example: "localhost"
                      ip:
                        type: string
                        example: "127.0.0.1"
                      port:
                        type: integer
                        example: 22
                      pos:
                        type: integer
                        example: 0
                      server_id:
                        type: integer
                        example: 1
                  shared:
                    type: integer
                    description: Indicates whether the Agent is shared or not
                    example: 0
                  uuid:
                    type: string
                    description: A unique identifier for the Agent
                    format: uuid
                    example: cf2cc8d2-4c44-48d1-9ed3-f6f49f8327fa
        """
        try:
            if g.user_params['role'] == 1:
                group = int(self.json_data['group_id'])
            else:
                group = int(g.user_params['group_id'])
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get group')
        agents = smon_sql.get_agents(group)
        if self.is_api:
            agent_list = []
            for agent in agents:
                agent_dict = model_to_dict(agent)
                agent_list.append(agent_dict)
            return jsonify(agent_list)
        else:
            kwargs = {
                'agents': smon_sql.get_agents(group),
                'lang': roxywi_common.get_user_lang_for_flask(),
                'smon_status': tools_common.is_tool_active('rmon-server'),
            }

            data = render_template('smon/agents.html', **kwargs)
            return jsonify({'status': 'ok', 'data': data})
