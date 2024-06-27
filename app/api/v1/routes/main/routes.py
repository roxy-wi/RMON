from flask import jsonify, request
from flask_jwt_extended import get_jwt
from flask_jwt_extended import jwt_required

from app import jwt
from app.api.v1.routes.main import bp
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common


@jwt.expired_token_loader
def my_expired_token_callback(jwt_header, jwt_payload):
    return jsonify(code="dave", err="I can't let you do that"), 401


@jwt.unauthorized_loader
def custom_unauthorized_response(_err):
    return jsonify(code="dave1", err=f"I can't let you do that: {_err}"), 401


@bp.route('/hello')
def hello():
    return jsonify({'hello': 'world'})


@bp.post('/login')
def do_login():
    try:
        login = request.json.get('login')
        password = request.json.get('password')
    except Exception:
        return roxywi_common.handle_json_exceptions('', 'There is no login or password')
    try:
        user_params = roxywi_auth.check_user_password(login, password)
    except Exception as e:
        return roxywi_common.handle_json_exceptions(e, ''), 401
    access_token = roxywi_auth.create_jwt_token(user_params)
    return jsonify(access_token=access_token)


@bp.route('/private')
@jwt_required()
def private():
    try:
        claims = get_jwt()
    except Exception as e:
        print(f'jwt bad: {e}')
    return jsonify(claims)
