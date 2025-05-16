from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify, request, g
from playhouse.shortcuts import model_to_dict
from flask_pydantic import validate

import app.modules.db.smon as smon_sql
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.smon_agent as smon_agent
from app.middleware import get_user_params, check_group, page_for_admin
from app.modules.db.db_model import InstallationTasks
from app.modules.roxywi.exception import RoxywiResourceNotFound
from app.modules.roxywi.class_models import BaseResponse, RmonAgent, GroupQuery, TaskAcceptedPostResponse, TaskAcceptedOtherResponse
from app.modules.common.common_classes import SupportClass


class AgentView(MethodView):
    method_decorators = ["GET", "POST", "PUT", "PATCH", "DELETE"]
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

    @staticmethod
    def get(agent_id: int):
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
          202:
            description: Task to installation accepted successfully
            schema:
              type: object
              properties:
                tasks_ids:
                  type: array
                  description: ID of the requested task
                  items:
                    type: integer
                id:
                  type: integer
                  description: ID of the agent created in the system
                status:
                  type: string
                  description: Current status of the task
          400:
            description: Invalid payload received
        """
        try:
            last_id, task_id = smon_agent.add_agent(body)
            return TaskAcceptedPostResponse(id=last_id, tasks_ids=[task_id]).model_dump(mode='json'), 202
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
          202:
            description: Task to installation accepted successfully
            schema:
              type: object
              properties:
                tasks_ids:
                  type: array
                  description: ID of the requested task
                  items:
                    type: integer
                id:
                  type: integer
                  description: ID of the agent created in the system
                status:
                  type: string
                  description: Current status of the task
          400:
            description: Invalid payload received
        """
        try:
            task_id = smon_agent.update_agent(agent_id, body)
            if body.reconfigure:
                return TaskAcceptedOtherResponse(tasks_ids=[task_id]).model_dump(mode='json'), 202
            return BaseResponse().model_dump(mode='json'), 201
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot update agent')

    @validate(query=GroupQuery)
    def patch(self, agent_id: int, query: GroupQuery):
        """
        Reconfigure agent.
        ---
        tags:
          - Agent
        parameters:
        - in: 'query'
          name: 'group_id'
          description: 'Group ID. For superAdmin only'
          required: false
          type: 'integer'
        - in: 'path'
          name: 'agent_id'
          description: 'ID of the agent to remove'
          required: true
          type: 'integer'
        responses:
          202:
            description: Task to installation accepted successfully
            schema:
              type: object
              properties:
                tasks_ids:
                  type: array
                  description: ID of the requested task
                  items:
                    type: integer
                id:
                  type: integer
                  description: ID of the agent created in the system
                status:
                  type: string
                  description: Current status of the task
          400:
            description: Invalid ID supplied
          404:
            description: Agent not found
        """
        group_id = SupportClass.return_group_id(query)
        try:
            smon_sql.get_agent_with_group(agent_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get agent')
        try:
            task_id = smon_agent.reconfigure_agent(agent_id)
            return TaskAcceptedOtherResponse(tasks_ids=[task_id]).model_dump(mode='json'), 202
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot reconfigure agent')

    @staticmethod
    def delete(agent_id: int):
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
          202:
            description: Task to installation accepted successfully
            schema:
              type: object
              properties:
                tasks_ids:
                  type: array
                  description: ID of the requested task
                  items:
                    type: integer
                id:
                  type: integer
                  description: ID of the agent created in the system
                status:
                  type: string
                  description: Current status of the task
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
            task_id = smon_agent.delete_agent(agent_id)
            smon_sql.delete_agent(agent_id)
            return TaskAcceptedOtherResponse(tasks_ids=[task_id]).model_dump(mode='json'), 202
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot delete agent')


class AgentsView(MethodView):
    method_decorators = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate()
    def get(self, query: GroupQuery):
        """
        Get Agent information by Group ID.
        ---
        tags:
          - Agent
        parameters:
        - in: 'query'
          name: 'group_id'
          description: 'Group ID. For superAdmin only'
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
        agent_list = [model_to_dict(agent, recurse=False) for agent in agents]
        return jsonify(agent_list)


class ReconfigureAgentView(MethodView):
    method_decorators = ["POST"]
    decorators = [jwt_required(), get_user_params(), check_group(), page_for_admin(level=2)]

    @validate(query=GroupQuery)
    def post(self, agent_id: int, query: GroupQuery):
        """
        Reconfigure agent.
        ---
        tags:
          - Agent
        parameters:
        - in: 'query'
          name: 'group_id'
          description: 'Group ID. For superAdmin only'
          required: false
          type: 'integer'
        - in: 'path'
          name: 'agent_id'
          description: 'ID of the agent to remove'
          required: true
          type: 'integer'
        responses:
          201:
            description: Agent successfully reconfigured
          400:
            description: Invalid ID supplied
          404:
            description: Agent not found
        """
        group_id = SupportClass.return_group_id(query)
        try:
            smon_sql.get_agent_with_group(agent_id, group_id)
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get agent')
        try:
            task_id = smon_agent.reconfigure_agent(agent_id)
            return TaskAcceptedOtherResponse(tasks_ids=[task_id]).model_dump(mode='json'), 202
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot reconfigure agent')


class AgentTaskStatusView(MethodView):
    method_decorators = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @staticmethod
    def get(task_id: int):
        """
        Get task status
        ---
        summary: Get task status
        description: Retrieve the status and details of a specific task by its task ID.
        tags:
          - Task status
        parameters:
          - name: task_id
            in: path
            description: The ID of the task to retrieve
            required: true
            schema:
              type: integer
        responses:
          200:
            description: Task details retrieved successfully
            schema:
              type: object
              properties:
                task_id:
                  type: integer
                  description: ID of the requested task
                status:
                  type: string
                  description: Current status of the task
                service_name:
                  type: string
                  description: Name of the service related to the task
                error:
                  type: string
                  nullable: true
                  description: Error message, if any
                server:
                  type: string
                  description: Hostname of the server associated with the task
          404:
            description: Task not found
          401:
            description: Unauthorized - token is missing or invalid
        """
        try:
            task = InstallationTasks.get(id=task_id)
        except InstallationTasks.DoesNotExist:
            return RoxywiResourceNotFound
        except Exception as e:
            return roxywi_common.handler_exceptions_for_json_data(e, 'Cannot get agent task')
        return jsonify(
            {
                'task_id': task_id,
                'status': task.status,
                'service_name': task.service_name,
                'error': task.error,
                'server': task.server_id.hostname,
            }
        ), 200
