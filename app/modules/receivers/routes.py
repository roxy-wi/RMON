from flask import Blueprint, g, jsonify, render_template, request
from flask_jwt_extended import jwt_required

from app.middleware import get_user_params, page_for_admin
from app.modules.client_telemetry.http import read_body, register_errors
from app.modules.db.db_model import Server, UserGroups
from app.modules.receivers import deployment, service
from app.modules.receivers.models import ReceiverEndpoint, ResultServer
from app.modules.receivers.schemas import EndpointInput, RoutingInput, ServerInput
from app.modules.roxywi.common import get_user_lang_for_flask

api = Blueprint('receivers_api', __name__, url_prefix='/api/v1.0/receivers')
pages = Blueprint('receivers', __name__)
register_errors(api)


@api.before_request
@jwt_required()
@get_user_params()
def authorize():
    user = g.user_params
    if not UserGroups.select().where((UserGroups.user_id == user['user_id']) &
                                      (UserGroups.user_group_id == user['group_id'])).exists():
        service.fail(403, 'group_denied', 'Select a group you belong to')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and int(user['role']) > 2:
        service.fail(403, 'read_only', 'Your role allows viewing receiver addresses only')


@api.after_request
def no_store(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def group():
    return int(g.user_params['group_id'])


def is_admin():
    return int(g.user_params['role']) == 1


def require_installation_admin():
    if not is_admin():
        service.fail(403, 'administrator_required', 'A system administrator must install or manage result servers')


@pages.get('/rmon/servers')
@jwt_required()
@get_user_params()
@page_for_admin(level=3)
def index():
    return render_template('receivers/servers.html', lang=get_user_lang_for_flask())


@api.get('/configuration')
def configuration():
    address_query = ReceiverEndpoint.select().where((ReceiverEndpoint.group == group()) | ReceiverEndpoint.shared)
    server_query = ResultServer.select().join(Server).where(Server.group_id == str(group()))
    return jsonify(endpoints=[service.endpoint_json(e) for e in address_query.order_by(ReceiverEndpoint.id).limit(1000)],
                   servers=[deployment.server_json(s) for s in server_query.order_by(ResultServer.id).limit(1000)],
                   hosts=[{'id': h.server_id, 'name': h.hostname, 'ip': h.ip} for h in Server.select().where(
                       Server.group_id == str(group())).order_by(Server.hostname).limit(1000)] if is_admin() else [],
                   defaults=service.defaults(group()), deployment=deployment.metadata() if is_admin() else {},
                   can_install=is_admin(), can_edit=int(g.user_params['role']) <= 2)


@api.route('/endpoints', methods=['GET', 'POST'])
def endpoints():
    if request.method == 'POST':
        value = service.save_endpoint(read_body(EndpointInput), group(), admin=is_admin())
        return jsonify(service.endpoint_json(value)), 201
    values = ReceiverEndpoint.select().where((ReceiverEndpoint.group == group()) | ReceiverEndpoint.shared)
    return jsonify(items=[service.endpoint_json(e) for e in values.order_by(ReceiverEndpoint.name).limit(1000)])


@api.route('/endpoints/<int:endpoint_id>', methods=['PUT', 'DELETE'])
def endpoint_detail(endpoint_id):
    value = service.endpoint(endpoint_id, group(), owner=True, admin=is_admin())
    if request.method == 'DELETE':
        service.delete_endpoint(value)
        return '', 204
    value = service.save_endpoint(read_body(EndpointInput), group(), endpoint_id=endpoint_id, admin=is_admin())
    return jsonify(service.endpoint_json(value))


@api.route('/defaults', methods=['GET', 'PUT'])
def default_endpoints():
    if request.method == 'PUT':
        body = read_body(RoutingInput)
        service.save_defaults(group(), body.endpoint_ids)
    return jsonify(endpoint_ids=service.defaults(group()))


@api.post('/servers')
def install_server():
    require_installation_admin()
    server, task = deployment.configure(read_body(ServerInput), group(), g.user_params['user_id'])
    return jsonify(id=server.id, task_id=task, status='queued'), 202


@api.put('/servers/<int:server_id>')
def update_server(server_id):
    require_installation_admin()
    server, task = deployment.configure(read_body(ServerInput), group(), g.user_params['user_id'], server_id)
    return jsonify(id=server.id, task_id=task, status='queued'), 202


@api.post('/servers/<int:server_id>/actions/<operation>')
def server_action(server_id, operation):
    require_installation_admin()
    server = deployment.get_server(server_id, group(), admin=True)
    task = deployment.action(server, operation, g.user_params['user_id'])
    return jsonify(task_id=task, status='queued'), 202
