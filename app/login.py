from flask import render_template, request, redirect, make_response
from flask_login import login_url
from flask_jwt_extended import unset_jwt_cookies, jwt_required

from app import app
import app.modules.db.user as user_sql
import app.modules.roxywi.roxy as roxy
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common


@app.before_request
def check_login():
    if request.endpoint not in (
            'login_page', 'static', 'main.show_roxywi_version', 'smon.show_smon_status_page', 'smon.smon_history_statuses_avg',
            'smon.smon_history_statuses', 'smon.agent_get_checks', 'smon.get_check_status', 'smon.smon_history_metric', 'api'
    ) and 'api' not in request.url:
        try:
            user_params = roxywi_common.get_users_params()
        except Exception as e:
            print(e)
            return redirect(login_url('login_page', next_url=request.url))

        if not user_sql.is_user_active(user_params['user_id']):
            return redirect(login_url('login_page', next_url=request.url))

        try:
            roxywi_auth.check_login(user_params['user_uuid'])
        except Exception:
            return redirect(login_url('login_page', next_url=request.url))


@app.after_request
def redirect_to_login(response):
    if 'api' not in str(request.blueprint):
        if response.status_code == 401:
            return redirect(login_url('login_page', next_url=request.url))
    return response


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'GET':
        try:
            lang = roxywi_common.get_user_lang_for_flask()
        except Exception:
            lang = 'en'

        return render_template('login.html', lang=lang)
    elif request.method == 'POST':
        next_url = request.args.get('next') or request.form.get('next')
        login = request.json.get('login')
        password = request.json.get('pass')

        try:
            roxy.update_plan()
        except Exception:
            pass

        try:
            user_params = roxywi_auth.check_user_password(login, password)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot check login password'), 200

        try:
            return roxywi_auth.do_login(user_params['uuid'], user_params['group'], user_params['user'], next_url)
        except Exception as e:
            return roxywi_common.handle_json_exceptions(e, 'Cannot do login'), 200


@app.route('/logout', methods=['GET', 'POST'])
@jwt_required()
def logout():
    resp = make_response(redirect('/', 302))
    unset_jwt_cookies(resp)
    return resp
