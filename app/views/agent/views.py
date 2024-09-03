from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify, request, g
from playhouse.shortcuts import model_to_dict
from flask_pydantic import validate

import app.modules.db.smon as smon_sql
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.smon_agent as smon_agent
from app.middleware import get_user_params, check_group
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.roxywi.class_models import BaseResponse, IdResponse, RmonAgent, GroupQuery
from app.modules.common.common_classes import SupportClass

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
        if request.method not in ('GET', 'DELETE'):
            self.json_data = request.get_json()
        else:
            self.json_data = None

    def get(self, agent_id: int):
        """
        Get an agent
        ---
        tags:
          - Agent
        parameters:
          - in: 'path'
            name: 'agent_id'
            description: 'ID of the agent to update'
            required: true
            type: 'integer'
        responses:
          200:
            description: Information about an agent
            schema:
              type: array
              items:
                id: Agent
                properties:
                  description:
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
                    type: integer
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
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get group id')
        try:
            agents = smon_sql.get_agent_with_group(agent_id, group)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get agent')
        agent_list = []
        for agent in agents:
            agent_dict = model_to_dict(agent, recurse=False)
            agent_list.append(agent_dict)
        try:
            if len(agent_list) == 0:
                raise RoxywiResourceNotFound
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, '')
        return jsonify(agent_dict)

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
                description:
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
            type: 'integer'
          - in: body
            name: body
            schema:
              id: AgentUpdate
              required:
                - name
                - server_id
                - port
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
                description:
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

    def delete(self, agent_id: int):
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
            _ = smon_sql.get_agent_uuid(agent_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get agent uuid')

        try:
            smon_agent.delete_agent(agent_id)
            smon_sql.delete_agent(agent_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot delete agent')


class AgentsView(MethodView):
    method_decorators = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate()
    def get(self, query: GroupQuery):
        """
        Get Agent information by Group ID.
        SuperAdmin can get by groups. Admin roles can get users only from its current group.
        ---
        tags:
          - Agent
        parameters:
        - in: 'query'
          name: 'group_id'
          description: 'ID of the group to list users. For superAdmin only'
          required: false
          type: 'integer'
        responses:
          200:
            description: A list of agents
            schema:
              type: array
              items:
                id: Agent
                properties:
                  description:
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
                      description:
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
        group_id = SupportClass.return_group_id(query)
        agents = smon_sql.get_agents(group_id)
        agent_list = []
        for agent in agents:
            agent_dict = model_to_dict(agent)
            agent_list.append(agent_dict)
        return jsonify(agent_list)
