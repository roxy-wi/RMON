from flask.views import MethodView
from flask_jwt_extended import jwt_required
from flask import render_template, jsonify, request, g

import app.modules.db.sql as sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.common.common as common
import app.modules.roxywi.user as roxywi_user
import app.modules.roxywi.common as roxywi_common
from app.middleware import get_user_params, page_for_admin


class UserView(MethodView):
    methods = ["POST", "PUT", "DELETE"]
    decorators = [jwt_required(), get_user_params(), page_for_admin(level=2)]

    def __init__(self, is_api=False):
        self.json_data = request.get_json()
        self.is_api = is_api

    def post(self):
        try:
            email = common.checkAjaxInput(self.json_data['email'])
            password = common.checkAjaxInput(self.json_data['password'])
            role = int(self.json_data['role'])
            new_user = common.checkAjaxInput(self.json_data['username'])
            enabled = int(self.json_data['enabled'])
            group_id = int(self.json_data['user_group'])
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create user')
        lang = roxywi_common.get_user_lang_for_flask()
        current_user_role_id = g.user_params['role']
        if not roxywi_common.check_user_group_for_flask():
            return roxywi_common.handle_json_exceptions('Wrong group', 'RMON server', '')
        if current_user_role_id > role:
            return roxywi_common.handle_json_exceptions('Wrong role', 'RMON server', '')
        try:
            user_id = roxywi_user.create_user(new_user, email, password, role, enabled, group_id)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot create a new user')
        else:
            if self.is_api:
                return jsonify({'status': 'created'})
            else:
                return jsonify({'status': 'created', 'id': user_id, 'data': render_template(
                    'ajax/new_user.html', users=user_sql.select_users(user=new_user), groups=group_sql.select_groups(),
                    roles=sql.select_roles(), adding=1, lang=lang
                )})

    def put(self):
        try:
            user_id = int(self.json_data['user_id'])
            user_name = common.checkAjaxInput(self.json_data['username'])
            email = common.checkAjaxInput(self.json_data['email'])
            enabled = int(self.json_data['enabled'])
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot update user')
        if roxywi_common.check_user_group_for_flask():
            try:
                user_sql.update_user_from_admin_area(user_name, email, user_id, enabled)
            except Exception as e:
                return roxywi_common.handle_json_exceptions(e, 'Cannot update user')
            roxywi_common.logging(user_name, ' has been updated user ', roxywi=1, login=1)
            return jsonify({'status': 'updated'})

    def delete(self):
        try:
            user_id = int(self.json_data['user_id'])
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot delete user')
        try:
            roxywi_user.delete_user(user_id)
            return jsonify({'status': 'deleted'})
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, f'Cannot delete the user {user_id}')
