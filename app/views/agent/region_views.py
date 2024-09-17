from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import jsonify
from playhouse.shortcuts import model_to_dict
from flask_pydantic import validate

import app.modules.db.smon as smon_sql
import app.modules.db.region as region_sql
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
from app.middleware import get_user_params, check_group
from app.modules.roxywi.class_models import BaseResponse, IdResponse, GroupQuery, RegionRequest
from app.modules.common.common_classes import SupportClass


class RegionView(MethodView):
    method_decorators = ["GET", "POST", "PUT", "DELETE"]
    decorators = [jwt_required(),  get_user_params(), check_group()]

    @validate(query=GroupQuery)
    def get(self, region_id: int, query: GroupQuery):
        group_id = SupportClass.return_group_id(query)
        try:
            region = region_sql.get_region_with_group(region_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find the region')

        return jsonify(model_to_dict(region))

    @validate(body=RegionRequest)
    def post(self, body: RegionRequest):
        roxywi_auth.page_for_admin(level=2)
        group_id = SupportClass.return_group_id(body)
        body.group_id = group_id
        try:
            last_id = region_sql.create_region(body)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create the region')
        try:
            for agent in body.agents:
                smon_sql.update_agent(agent, region_id=last_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot add agents to the new region')

        return IdResponse(id=last_id).model_dump(mode='json'), 201

    @validate(body=RegionRequest)
    def put(self, region_id: int, body: RegionRequest):
        roxywi_auth.page_for_admin(level=2)
        group_id = SupportClass.return_group_id(body)
        body.group_id = group_id
        try:
            region_sql.update_region(body, region_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create the region')

        try:
            agents = smon_sql.get_agents_by_region(region_id)
            for agent in agents:
                smon_sql.update_agent(agent, region_id=None)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update agents')

        try:
            for agent in body.agents:
                smon_sql.update_agent(agent, region_id=region_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot add agents to the region')

        return BaseResponse().model_dump(mode='json'), 201

    @staticmethod
    @validate(query=GroupQuery)
    def delete(region_id: int, query: GroupQuery):
        roxywi_auth.page_for_admin(level=2)
        group_id = SupportClass.return_group_id(query)
        try:
            region_sql.get_region_with_group(region_id, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot find the region')

        try:
            region_sql.delete_region(region_id)
            return BaseResponse().model_dump(mode='json'), 204
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete the region')


class RegionListView(MethodView):
    method_decorators = ["GET"]
    decorators = [jwt_required(), get_user_params(), check_group()]

    @validate(query=GroupQuery)
    def get(self, query: GroupQuery):
        group_id = SupportClass.return_group_id(query)
        try:
            regions = region_sql.select_regions_by_group(group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot get regions')

        return jsonify([model_to_dict(region) for region in regions])
