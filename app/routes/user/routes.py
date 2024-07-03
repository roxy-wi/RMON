import json

from flask import request
from flask_jwt_extended import jwt_required

from app.routes.user import bp
import app.modules.db.group as group_sql
import app.modules.common.common as common
import app.modules.roxywi.user as roxywi_user
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
from app.views.user.views import UserView


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
def update_password():
    password = request.form.get('updatepassowrd')
    uuid = request.form.get('uuid')
    user_id_from_get = request.form.get('id')

    return roxywi_user.update_user_password(password, uuid, user_id_from_get)


@bp.route('/groups/<int:user_id>')
def show_user_groups_and_roles(user_id):
    lang = roxywi_common.get_user_lang_for_flask()

    return roxywi_user.show_user_groups_and_roles(user_id, lang)


@bp.post('/groups/save')
def change_user_groups_and_roles():
    user = common.checkAjaxInput(request.form.get('changeUserGroupsUser'))
    groups_and_roles = json.loads(request.form.get('jsonDatas'))
    user_uuid = request.cookies.get('uuid')

    return roxywi_user.save_user_group_and_role(user, groups_and_roles, user_uuid)


@bp.route('/group/name/<int:group_id>')
def get_group_name_by_id(group_id):
    return group_sql.get_group_name_by_id(group_id)
