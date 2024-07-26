import json
import time

from flask import render_template, request, jsonify, g, Response, stream_with_context
from flask_jwt_extended import jwt_required

from app.routes.smon import bp
from app.middleware import get_user_params
import app.modules.db.history as history_sql
import app.modules.db.smon as smon_sql
import app.modules.db.channel as channel_sql
import app.modules.common.common as common
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.smon as smon_mod
import app.modules.tools.common as tools_common


@bp.route('/dashboard')
@jwt_required()
@get_user_params()
def smon_main_dashboard():
    """
    Dashboard route for the smon tool.

    :return: The rendered dashboard template with the necessary parameters.
    :rtype: flask.Response
    """
    roxywi_common.check_user_group_for_flask()
    group_id = g.user_params['group_id']

    kwargs = {
        'lang': g.user_params['lang'],
        'smon': smon_sql.smon_list(group_id),
        'group': group_id,
        'smon_groups': smon_sql.select_smon_groups(group_id),
        'smon_status': tools_common.is_tool_active('rmon-server'),
        'telegrams': channel_sql.get_user_receiver_by_group('telegram', group_id),
        'slacks': channel_sql.get_user_receiver_by_group('slack', group_id),
        'pds': channel_sql.get_user_receiver_by_group('pd', group_id),
        'mms': channel_sql.get_user_receiver_by_group('mm', group_id),
        'sort': request.args.get('sort', None)
    }

    return render_template('smon/dashboard.html', **kwargs)


@bp.route('/dashboard/<int:smon_id>/<int:check_id>')
@jwt_required()
@get_user_params()
def smon_dashboard(smon_id, check_id):
    """
    :param smon_id: The ID of the RMON (Server Monitoring) service.
    :param check_id: The ID of the check associated with the RMON service.
    :return: The rendered RMON dashboard template.

    This method is used to render the RMON dashboard template for a specific RMON service and check. It retrieves relevant data from the database and passes it to the template for rendering
    *.

    The `smon_id` parameter specifies the ID of the RMON service.
    The `check_type_id` parameter specifies the ID of the check associated with the RMON service.

    The method performs the following steps:
    1. Checks user group for Flask access.
    2. Retrieves the RMON object from the database using the `smon_id` and `check_type_id` parameters.
    3. Gets the current date and time using the `get_present_time()` function from the common module.
    4. Sets the initial value of `cert_day_diff` as 'N/A'.
    5. Tries to calculate the average response time for the RMON service using the `get_avg_resp_time` function from the SQL module. If an exception occurs, the average response time is
    * set to 0.
    6. Tries to retrieve the last response time for the RMON service and check using the `get_last_smon_res_time_by_check` function from the SQL module. If an exception occurs, the last
    * response time is set to 0.
    7. Iterates over the retrieved RMON object and checks if the SSL expiration date is not None. If it is not None, calculates the difference in days between the expiration date and the
    * present date using the `datetime.strptime()` function and assigns it to `cert_day_diff`.
    8. Constructs a dictionary (`kwargs`) containing various parameters required for rendering the template, including `lang`, `smon`, `group`, `user_subscription`, `check
    *_interval`, `uptime`, `avg_res_time`, `smon_name`, `cert_day_diff`, `check_type_id`, `dashboard_id`, and `last_resp_time`.
    9. Renders the RMON history template ('include/smon/smon_history.html') using the `render_template` function from Flask, passing the `kwargs` dictionary as keyword arguments.
    """
    roxywi_common.check_user_group_for_flask()
    smon = smon_sql.select_one_smon(smon_id, check_id)
    cert_day_diff = 'N/A'
    avg_res_time = smon_mod.get_average_response_time(smon_id, check_id)

    try:
        last_resp_time = round(smon_sql.get_last_smon_res_time_by_check(smon_id, check_id), 2)
    except Exception:
        last_resp_time = 0

    for s in smon:
        if s.smon_id.ssl_expire_date is not None:
            cert_day_diff = smon_mod.get_ssl_expire_date(s.smon_id.ssl_expire_date)

    kwargs = {
        'lang': g.user_params['lang'],
        'smon': smon,
        'group': g.user_params['group_id'],
        'user_subscription': roxywi_common.return_user_subscription(),
        'uptime': smon_mod.check_uptime(smon_id),
        'avg_res_time': avg_res_time,
        'smon_name': smon_sql.get_smon_service_name_by_id(smon_id),
        'cert_day_diff': cert_day_diff,
        'check_type_id': check_id,
        'dashboard_id': smon_id,
        'last_resp_time': last_resp_time,
        'agents': smon_sql.get_agents(g.user_params['group_id'])
    }

    return render_template('include/smon/smon_history.html', **kwargs)


@bp.get('/groups')
@jwt_required()
@get_user_params()
def get_groups():
    groups = smon_sql.select_smon_groups(g.user_params['group_id'])
    smon_groups = ''
    for group in groups:
        group_name = group.name.replace("'", "")
        smon_groups += f'{group_name}\n'
    return smon_groups


@bp.route('/status-page', methods=['GET', 'POST', 'DELETE', 'PUT'])
@jwt_required()
@get_user_params()
def status_page():
    """
       This function handles the '/status-page' route with methods GET, POST, DELETE, and PUT.
       It requires the user to be logged in and retrieves user parameters.

       :return:
          - GET method: Renders the 'smon/manage_status_page.html' template with the following keyword arguments:
              - 'lang': The language from user parameters
              - 'smon': The list of smon from sql.smon_list() using the 'group_id' from user parameters
              - 'pages': The status pages from sql.select_status_pages() using the 'group_id' from user parameters
              - 'smon_status': The status of the 'rmon-server' tool from tools_common.is_tool_active()
              - 'user_subscription': The user subscription from roxywi_common.return_user_subscription()
          - POST method: Creates a status page with the following parameters:
              - 'name': The name of the status page
              - 'slug': The slug of the status page
              - 'desc': The description of the status page
              - 'checks': The checks for the status page
          - PUT method: Edits a status page with the following parameters:
              - 'page_id': The ID of the status page
              - 'name': The updated name of the status page
              - 'slug': The updated slug of the status page
              - 'desc': The updated description of the status page
              - 'checks': The updated checks for the status page
          - DELETE method: Deletes a status page with the following parameter:
              - 'page_id': The ID of the status page

       The function returns different values based on the method used:
          - POST method: Returns the result of smon_mod.create_status_page() for creating the status page or an exception message in case of an error.
          - PUT method: Returns the result of smon_mod.edit_status_page() for editing the status page or an exception message in case of an error.
          - DELETE method: Returns 'ok' if the status page is successfully deleted or an exception message in case of an error.

       .. note::
          - The checks for the status page should not be empty. If no checks are selected, it returns an error message.
          - Any exceptions raised during the process will be returned as exception messages.
    """
    if request.method == 'GET':
        kwargs = {
            'lang': g.user_params['lang'],
            'smon': smon_sql.smon_list(g.user_params['group_id']),
            'pages': smon_sql.select_status_pages(g.user_params['group_id']),
            'smon_status': tools_common.is_tool_active('rmon-server'),
            'user_subscription': roxywi_common.return_user_subscription()
        }

        return render_template('smon/manage_status_page.html', **kwargs)
    elif request.method == 'POST':
        name = common.checkAjaxInput(request.form.get('name'))
        slug = common.checkAjaxInput(request.form.get('slug'))
        desc = common.checkAjaxInput(request.form.get('desc'))
        checks = json.loads(request.form.get('checks'))

        if not len(checks['checks']):
            return 'error: Please check Checks for Status page'

        try:
            return smon_mod.create_status_page(name, slug, desc, checks['checks'])
        except Exception as e:
            return f'{e}'
    elif request.method == 'PUT':
        page_id = int(request.form.get('page_id'))
        name = common.checkAjaxInput(request.form.get('name'))
        slug = common.checkAjaxInput(request.form.get('slug'))
        desc = common.checkAjaxInput(request.form.get('desc'))
        checks = json.loads(request.form.get('checks'))

        if not len(checks['checks']):
            return 'error: Please check Checks for Status page'

        try:
            return smon_mod.edit_status_page(page_id, name, slug, desc, checks['checks'])
        except Exception as e:
            return f'{e}'
    elif request.method == 'DELETE':
        page_id = int(request.form.get('page_id'))
        try:
            smon_sql.delete_status_page(page_id)
        except Exception as e:
            return f'{e}'
        else:
            return 'ok'


@bp.route('/status/checks/<int:page_id>')
@jwt_required()
def get_checks(page_id):
    """
    :param page_id: The ID of the page for which to fetch the checks.
    :return: A JSON response with an array of check IDs.

    """
    returned_check = []
    try:
        checks = smon_sql.select_status_page_checks(page_id)
    except Exception as e:
        return f'error: Cannot get checks: {e}'

    for _check in checks:
        returned_check.append(str(_check.check_id))

    return jsonify(returned_check)


@bp.route('/status/<slug>')
def show_smon_status_page(slug):
    slug = common.checkAjaxInput(slug)

    return smon_mod.show_status_page(slug)


@bp.route('/status/avg/<int:page_id>')
def smon_history_statuses_avg(page_id):
    return smon_mod.avg_status_page_status(page_id)


@bp.route('/history')
@jwt_required()
@get_user_params()
def smon_history():
    roxywi_common.check_user_group_for_flask()

    kwargs = {
        'lang': g.user_params['lang'],
        'smon': history_sql.alerts_history('RMON', g.user_params['group_id']),
        'smon_status': tools_common.is_tool_active('rmon-server'),
        'user_subscription': roxywi_common.return_user_subscription(),
        'action': 'smon'
    }

    return render_template('smon/history.html', **kwargs)


@bp.route('/history/host/<server_ip>')
@jwt_required()
@get_user_params()
def smon_host_history(server_ip):
    roxywi_common.check_user_group_for_flask()
    needed_host = common.checkAjaxInput(server_ip)
    if ' ' in needed_host:
        needed_host = f"'{needed_host}'"
    smon_status = tools_common.is_tool_active('rmon-server')
    smon = history_sql.alerts_history('RMON', g.user_params['group_id'], host=needed_host)
    user_subscription = roxywi_common.return_user_subscription()
    kwargs = {
        'lang': g.user_params['lang'],
        'smon': smon,
        'smon_status': smon_status,
        'user_subscription': user_subscription,
        'action': 'smon'
    }

    return render_template('smon/history.html', **kwargs)


@bp.route('/history/metric/<int:check_id>/<int:check_type_id>')
def smon_history_metric(check_id, check_type_id):
    return jsonify(smon_mod.history_metrics(check_id, check_type_id))


@bp.route('/history/metrics/stream/<int:check_id>/<int:check_type_id>')
@get_user_params()
def smon_history_metric_chart(check_id, check_type_id):
    """
    This method generates a streaming event chart for the history of a metric associated with a given check ID and check type ID.

    Parameters:
    - check_id (int): The ID of the check for which to generate the metric history chart.
    - check_type_id (int): The ID of the check type for the given check.

    Returns:
    - A Flask Response object with the streaming event chart.
    """

    def get_chart_data():
        """
        Return a generator that continuously yields chart data in JSON format for the specified check ID and check type ID.

        Parameters:
        - check_id (int): The ID of the check.
        - check_type_id (int): The ID of the check type.

        Returns:
        A generator that yields chart data in the format of a JSON string.
        """
        interval = 120
        while True:
            json_metric = {}
            is_enabled = 1
            chart_metrics = smon_sql.select_smon_history(check_id, 1)
            uptime = smon_mod.check_uptime(check_id)
            smon = smon_sql.select_one_smon(check_id, check_type_id)
            agents = smon_sql.get_agents(g.user_params['group_id'])
            avg_res_time = smon_mod.get_average_response_time(check_id, check_type_id)

            for s in smon:
                json_metric['updated_at'] = common.get_time_zoned_date(s.smon_id.updated_at)
                json_metric['name'] = str(s.smon_id.name)
                interval = s.interval
                is_enabled = s.smon_id.enabled
                if s.smon_id.ssl_expire_date is not None:
                    json_metric['ssl_expire_date'] = smon_mod.get_ssl_expire_date(s.smon_id.ssl_expire_date)
                else:
                    json_metric['ssl_expire_date'] = 'N/A'

                for agent in agents:
                    if agent.id == s.agent_id:
                        json_metric['agent'] = agent.name
                        break
                else:
                    json_metric['agent'] = 'None'

            for i in chart_metrics.iterator():
                json_metric['time'] = common.get_time_zoned_date(i.date, '%H:%M:%S')
                # json_metric['value'] = "{:.3f}".format(i.response_time)
                json_metric['value'] = i.response_time
                json_metric['mes'] = str(i.mes)
                json_metric['uptime'] = uptime
                json_metric['avg_res_time'] = avg_res_time
                json_metric['interval'] = interval
                json_metric['status'] = str(i.status) if is_enabled else 4
                if check_type_id == 2:
                    json_metric['name_lookup'] = str(i.name_lookup)
                    json_metric['connect'] = str(i.connect)
                    json_metric['app_connect'] = str(i.app_connect)
                    json_metric['pre_transfer'] = str(i.pre_transfer)
                    if float(i.redirect) <= 0:
                        json_metric['redirect'] = '0'
                    else:
                        json_metric['redirect'] = str(i.redirect)
                    if float(i.start_transfer) <= 0:
                        json_metric['start_transfer'] = '0'
                    else:
                        json_metric['start_transfer'] = str(i.start_transfer)
                    json_metric['m_download'] = str(i.download)
            yield f"data:{json.dumps(json_metric)}\n\n"
            time.sleep(interval)

    response = Response(stream_with_context(get_chart_data()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@bp.route('/history/statuses/<int:dashboard_id>')
def smon_history_statuses(dashboard_id):
    return smon_mod.history_statuses(dashboard_id)


@bp.route('/history/cur_status/<int:dashboard_id>/<int:check_id>')
@jwt_required()
def smon_history_cur_status(dashboard_id, check_id):
    return smon_mod.history_cur_status(dashboard_id, check_id)
