from flask_swagger import swagger
from flask import jsonify, request, render_template

from app import app, jwt
from app.api.v1.routes.main import bp
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
from app.views.server.views import ServerGroupView, ServerGroupsView, ServersView
from app.views.user.views import UsersView
from app.views.channel.views import ChannelView, ChannelsView
from app.views.admin.views import SettingsView

bp.add_url_rule('/users', view_func=UsersView.as_view('users'), methods=['GET'])
bp.add_url_rule('/groups', view_func=ServerGroupsView.as_view('groups'), methods=['GET'])
bp.add_url_rule('/servers', view_func=ServersView.as_view('servers'), methods=['GET'])


def register_api(view, endpoint, url, pk='check_id', pk_type='int'):
    view_func = view.as_view(endpoint)
    bp.add_url_rule(url, view_func=view_func, methods=['POST',])
    bp.add_url_rule(f'/{url}/<{pk_type}:{pk}>', view_func=view_func, methods=['GET', 'PUT', 'DELETE'])


register_api(ServerGroupView, 'group', '/group', 'group_id')


def register_api_with_group(view, endpoint, url_beg, pk='receiver', pk_type='int', pk_end='channel_id', pk_type_end='int'):
    view_func = view.as_view(endpoint, True)
    bp.add_url_rule(f'/{url_beg}/<any(telegram, slack, pd, mm):{pk}>', view_func=view_func, methods=['POST'])
    bp.add_url_rule(f'/{url_beg}/<any(telegram, slack, pd, mm):{pk}>/<{pk_type_end}:{pk_end}>', view_func=view_func, methods=['PUT', 'DELETE', 'GET', 'PATCH'])


register_api_with_group(ChannelView, 'channel', '/channel')
bp.add_url_rule('/channels/<any(telegram, slack, pd, mm):receiver>', view_func=ChannelsView.as_view('channels'), methods=['GET'])

bp.add_url_rule(
    '/settings',
    view_func=SettingsView.as_view('settings'),
    methods=['GET'],
    defaults={'section': None}
)

bp.add_url_rule(
    '/settings/<any(rmon, main, rabbitmq, ldap, monitoring, mail, logs):section>',
    view_func=SettingsView.as_view('settings_section'),
    methods=['GET', 'POST']
)


@jwt.expired_token_loader
def my_expired_token_callback(jwt_header, jwt_payload):
    return jsonify(error="Token is expired"), 401


@jwt.unauthorized_loader
def custom_unauthorized_response(_err):
    return jsonify(error="Authorize first"), 401


@bp.route("/spec")
def spec():
    swag = swagger(app)
    swag['info']['version'] = "1.0"
    swag['info']['title'] = "RMON API"
    return jsonify(swag)


@bp.route("/swagger")
def swagger_ui():
    return render_template('swagger.html')


@bp.post('/login')
def do_login():
    """
    Do log in
    ---
    tags:
      - Authentication
    description: This route is used to log into the system
    parameters:
      - name: body
        in: body
        schema:
          type: object
          properties:
            login:
              type: string
              required: true
              description: The user's login name
            password:
              type: string
              required: true
              description: The user's password
    responses:
      200:
        description: Login successfully, return a JWT token
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: JWT token for user authentication
      401:
        description: Authentication Error
    """
    try:
        login = request.json.get('login')
        password = request.json.get('password')
    except Exception as e:
        return roxywi_common.handler_exceptions_for_json_data(e, 'There is no login or password')
    try:
        user_params = roxywi_auth.check_user_password(login, password)
    except Exception as e:
        return roxywi_common.handle_json_exceptions(e, ''), 401
    access_token = roxywi_auth.create_jwt_token(user_params)
    return jsonify(access_token=access_token)
