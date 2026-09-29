"""Authenticated management and diagnostics; the public collector is separate."""
from flask import g, jsonify, request
from flask_jwt_extended import jwt_required

from app.api.v1.routes.client import bp
from app.middleware import get_user_params
from app.modules.client_telemetry import service
from app.modules.client_telemetry.http import read_body, register_errors
from app.modules.client_telemetry.models import ClientCheck, ClientDefinition, ClientKey, ClientObservation, ClientProject
from app.modules.client_telemetry.schemas import CheckInput, Definition, KeyInput, ProjectInput, ProjectState
from app.modules.db.db_model import Groups, UserGroups

register_errors(bp)


@bp.before_request
@jwt_required()
@get_user_params()
def authorize():
    user = g.user_params
    if not UserGroups.select().where((UserGroups.user_id == user['user_id'])
                                      & (UserGroups.user_group_id == user['group_id'])).exists():
        raise service.TelemetryError(403, 'group_denied', 'Select a group you belong to')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and int(user['role']) > 3:
        raise service.TelemetryError(403, 'read_only', 'Your role allows viewing client checks only')
    if any(not 1 <= value <= 2147483647 for value in (request.view_args or {}).values()):
        raise service.TelemetryError(404, 'resource_not_found', 'The requested resource was not found')


@bp.after_request
def no_store(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


def group_id(selected=None):
    active = int(g.user_params['group_id'])
    if selected is not None and selected != active and int(g.user_params['role']) != 1:
        raise service.TelemetryError(403, 'group_denied', 'Use the active group')
    selected = active if selected is None else selected
    if not Groups.select().where(Groups.group_id == selected).exists():
        raise service.TelemetryError(404, 'group_not_found', 'Group was not found')
    return selected


def project(project_id):
    query = ClientProject.select().where(ClientProject.id == project_id)
    if int(g.user_params['role']) != 1:
        query = query.where(ClientProject.group == g.user_params['group_id'])
    value = query.first()
    if value is None:
        raise service.TelemetryError(404, 'project_not_found', 'Project was not found')
    return value


def number_argument(name, default, minimum, maximum):
    value = request.args.get(name, str(default))
    if len(value) > 19 or not value.isascii() or not value.isdigit() or not minimum <= int(value) <= maximum:
        raise service.TelemetryError(422, 'invalid_query', f'{name} must be between {minimum} and {maximum}')
    return int(value)


def project_json(value):
    return {name: getattr(value, name) for name in ('id', 'group_id', 'name', 'description', 'enabled',
            'events_per_minute', 'requests_per_minute', 'bytes_per_minute', 'created_us')}


def check_json(value):
    return {name: getattr(value, name) for name in ('id', 'project_id', 'code', 'name', 'description', 'current_version')}


def key_json(value):
    return {name: getattr(value, name) for name in ('id', 'name', 'prefix', 'checks', 'environments', 'origins',
            'allow_no_origin', 'revoked', 'created_us', 'last_used_us')}


@bp.route('/projects', methods=['GET', 'POST'])
def projects():
    if request.method == 'POST':
        body = read_body(ProjectInput)
        result = service.create_project(body, group_id(body.group_id), g.user_params['user_id'])
        return jsonify(project_json(result)), 201
    selected = number_argument('group_id', int(g.user_params['group_id']), 1, 2147483647)
    after = number_argument('after_id', 0, 0, 2147483647)
    limit = number_argument('limit', 50, 1, 100)
    values = list(ClientProject.select().where((ClientProject.group == group_id(selected)) & (ClientProject.id > after))
                  .order_by(ClientProject.id).limit(limit + 1))
    return jsonify(items=[project_json(value) for value in values[:limit]],
                   next_after_id=values[limit - 1].id if len(values) > limit else None)


@bp.route('/projects/<int:project_id>', methods=['GET', 'PATCH'])
def project_detail(project_id):
    value = project(project_id)
    if request.method == 'PATCH':
        body = read_body(ProjectState)
        service.set_project_state(project_id, body.enabled, g.user_params['user_id'])
        value = project(project_id)
    return jsonify(project_json(value))


@bp.route('/projects/<int:project_id>/checks', methods=['GET', 'POST'])
def checks(project_id):
    project(project_id)
    if request.method == 'POST':
        body = read_body(CheckInput)
        return jsonify(check_json(service.create_check(project_id, body, g.user_params['user_id']))), 201
    after = number_argument('after_id', 0, 0, 2147483647)
    limit = number_argument('limit', 50, 1, 100)
    values = list(ClientCheck.select().where((ClientCheck.project == project_id) & (ClientCheck.id > after))
                  .order_by(ClientCheck.id).limit(limit + 1))
    return jsonify(items=[check_json(value) for value in values[:limit]],
                   next_after_id=values[limit - 1].id if len(values) > limit else None)


@bp.route('/projects/<int:project_id>/checks/<int:check_id>/definitions', methods=['GET', 'POST'])
def definitions(project_id, check_id):
    project(project_id)
    if not ClientCheck.select().where((ClientCheck.id == check_id) & (ClientCheck.project == project_id)).exists():
        raise service.TelemetryError(404, 'check_not_found', 'Check was not found')
    if request.method == 'POST':
        body = read_body(Definition)
        expected = request.headers.get('If-Match')
        if expected is not None:
            if expected.startswith('"') and expected.endswith('"'):
                expected = expected[1:-1]
            if not expected.isascii() or not expected.isdigit() or len(expected) > 3 or not 1 <= int(expected) <= 100:
                raise service.TelemetryError(422, 'invalid_version', 'If-Match must contain the definition version being edited')
            expected = int(expected)
        version = service.add_definition(project_id, check_id, body, g.user_params['user_id'], expected_version=expected)
        return jsonify(version=version), 201
    return jsonify(items=[{'version': row.version, 'definition': row.definition}
                          for row in ClientDefinition.select().where(ClientDefinition.check == check_id)
                          .order_by(ClientDefinition.version)])


@bp.route('/projects/<int:project_id>/keys', methods=['GET', 'POST'])
def keys(project_id):
    project(project_id)
    if request.method == 'POST':
        body = read_body(KeyInput)
        key, token = service.issue_key(project_id, body, g.user_params['user_id'])
        return jsonify(**key_json(key), project_key=token), 201
    after = number_argument('after_id', 0, 0, 2147483647)
    limit = number_argument('limit', 50, 1, 100)
    values = list(ClientKey.select().where((ClientKey.project == project_id) & (ClientKey.id > after))
                  .order_by(ClientKey.id).limit(limit + 1))
    return jsonify(items=[key_json(value) for value in values[:limit]],
                   next_after_id=values[limit - 1].id if len(values) > limit else None)


@bp.delete('/projects/<int:project_id>/keys/<int:key_id>')
def revoke(project_id, key_id):
    project(project_id)
    service.revoke_key(project_id, key_id, g.user_params['user_id'])
    return '', 204


@bp.get('/projects/<int:project_id>/events')
def recent_events(project_id):
    project(project_id)
    limit = number_argument('limit', 50, 1, 100)
    before = number_argument('before_id', 9223372036854775807, 1, 9223372036854775807)
    values = list(ClientObservation.select().where((ClientObservation.project == project_id)
                                                   & (ClientObservation.id < before))
                  .order_by(ClientObservation.id.desc()).limit(limit + 1))
    return jsonify(items=[{'id': value.id, 'received_us': value.received_us, 'event': value.event}
                          for value in values[:limit]],
                   next_before_id=values[limit - 1].id if len(values) > limit else None)


@bp.get('/projects/<int:project_id>/checks/<int:check_id>/report')
def check_report(project_id, check_id):
    from app.modules.client_telemetry import reports
    project(project_id)
    with reports.snapshot():
        check = ClientCheck.get_or_none((ClientCheck.id == check_id) & (ClientCheck.project == project_id))
        if check is None:
            raise service.TelemetryError(404, 'check_not_found', 'Check was not found')
        result = reports.build(check, request.args)
    return jsonify(result)


@bp.get('/projects/<int:project_id>/overview')
def project_overview(project_id):
    from app.modules.client_telemetry import reports
    project(project_id)
    after = number_argument('after_id', 0, 0, 2147483647)
    limit = number_argument('checks_limit', 20, 1, 50)
    with reports.snapshot():
        checks = list(ClientCheck.select().where((ClientCheck.project == project_id) & (ClientCheck.id > after))
                      .order_by(ClientCheck.id).limit(limit + 1))
        budget = reports.Budget()
        items = [{**check_json(check), 'report': reports.build(check, request.args, include_series=False, budget=budget)}
                 for check in checks[:limit]]
    return jsonify(items=items, next_after_id=checks[limit - 1].id if len(checks) > limit else None)
