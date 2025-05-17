from flask import render_template, request, redirect, make_response, abort
from flask_jwt_extended import unset_jwt_cookies, jwt_required

from app import app
import app.modules.db.user as user_sql
import app.modules.roxywi.roxy as roxy
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common


@app.before_request
def check_login():
    allowed_endpoints = (
        'login_page', 'static', 'main.show_roxywi_version', 'smon.show_smon_status_page', 'smon.smon_history_statuses_avg',
        'smon.smon_history_statuses', 'smon.agent_get_checks', 'smon.get_check_status', 'smon.smon_history_metric', 'api', 'favicon',
        'prometheus_metrics'
    )
    if 'api' not in request.url and request.endpoint not in allowed_endpoints:
        try:
            user_params = roxywi_common.get_users_params()
        except Exception as e:
            print(f'{e}')
            abort(401)

        if not user_sql.get_user_id(user_params['user_id']).enabled:
            print(f'error: User {user_params["user_id"]} is not active')
            abort(401, f'error: User {user_params["user_id"]} is not active')

        try:
            roxywi_auth.check_login(user_params['user_id'])
        except Exception as e:
            print(f'error: Cannot check login: {e}')
            abort(401)


@app.after_request
def redirect_to_login(response):
    return response


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        lang = roxywi_common.get_user_lang_for_flask()

        return render_template('login.html', lang=lang)
    elif request.method == 'POST':
        next_url = request.json.get('next')
        login = request.json.get('login')
        password = request.json.get('pass')

        try:
            roxy.update_plan()
        except Exception:
            pass

        try:
            user_params = roxywi_auth.check_user_password(login, password)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot check login password'), 401

        try:
            return roxywi_auth.do_login(user_params, next_url)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot do login'), 401
    return None


@app.route('/logout', methods=['GET', 'POST'])
@jwt_required()
def logout():
    resp = make_response(redirect('/', 302))
    unset_jwt_cookies(resp)
    return resp
