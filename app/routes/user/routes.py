import json

from flask import request, g
from flask_jwt_extended import jwt_required

from app.routes.user import bp
import app.modules.common.common as common
import app.modules.roxywi.user as roxywi_user
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
from app.views.user.views import UserView
from app.middleware import get_user_params
from app.modules.roxywi.class_models import BaseResponse, ErrorResponse


@bp.before_request
@jwt_required()
def before_request():
    """ Protect all the admin endpoints. """
    pass


bp.add_url_rule('', view_func=UserView.as_view('user'), methods=['POST'])


@bp.route('/ldap/<username>')
def get_ldap_email(username):
    roxywi_auth.page_for_admin(level=2)

    return roxywi_user.get_ldap_email(username)


@bp.post('/password')
@get_user_params()
def update_user_its_password():
    password = request.json.get('pass')

    try:
        roxywi_user.update_user_password(password, g.user_params['user_id'])
        return BaseResponse().model_dump(mode='json')
    except Exception as e:
        return ErrorResponse(error=str(e)).model_dump(mode='json'), 501


@bp.post('/password/<int:user_id>')
def update_user_password(user_id):
    password = request.json.get('pass')

    try:
        roxywi_user.update_user_password(password, user_id)
        return BaseResponse().model_dump(mode='json')
    except Exception as e:
        return ErrorResponse(error=str(e)).model_dump(mode='json'), 501


@bp.route('/groups/<int:user_id>')
def show_user_groups_and_roles(user_id):
    lang = roxywi_common.get_user_lang_for_flask()

    return roxywi_user.show_user_groups_and_roles(user_id, lang)


@bp.post('/groups/save')
def change_user_groups_and_roles():
    user = common.checkAjaxInput(request.form.get('changeUserGroupsUser'))
    groups_and_roles = json.loads(request.form.get('jsonDatas'))

    return roxywi_user.save_user_group_and_role(user, groups_and_roles)
