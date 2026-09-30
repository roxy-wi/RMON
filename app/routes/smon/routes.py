import json
import time

from flask import render_template, request, g, Response, stream_with_context, jsonify
from flask_jwt_extended import jwt_required
from flask_pydantic import validate

from app.modules.roxywi.class_models import EscapedString
from app.routes.smon import bp
from app.middleware import get_user_params
import app.modules.db.history as history_sql
import app.modules.db.smon as smon_sql
import app.modules.db.channel as channel_sql
import app.modules.common.common as common
import app.modules.roxywi.common as roxywi_common
from app.modules.subscription.access import (
    ALERT_HISTORY,
    MONITORING_HISTORY,
    STATUS_PAGES,
    feature_required,
    is_feature_available,
)
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
        'group': group_id,
        'smon_status': tools_common.is_tool_active('rmon-server'),
        'telegrams': channel_sql.get_user_receiver_by_group('telegram', group_id),
        'incidentrelay': channel_sql.get_user_receiver_by_group('incidentrelay', group_id),
        'slacks': channel_sql.get_user_receiver_by_group('slack', group_id),
        'pds': channel_sql.get_user_receiver_by_group('pd', group_id),
        'mms': channel_sql.get_user_receiver_by_group('mm', group_id),
        'emails': channel_sql.get_user_receiver_by_group('email', group_id),
    }

    return render_template('smon/dashboard.html', **kwargs)


@bp.get('/dashboard/data')
@jwt_required()
@get_user_params()
def dashboard_data():
    from app.modules.tools.dashboard import snapshot
    from app.modules.db.db_model import UserGroups
    from peewee import DatabaseError
    from flask import current_app
    user = g.user_params
    if not UserGroups.select().where((UserGroups.user_id == user['user_id']) &
                                     (UserGroups.user_group_id == user['group_id'])).exists():
        return jsonify(error='group_denied'), 403
    try:
        response = jsonify(snapshot(user['group_id'], include_history=is_feature_available(MONITORING_HISTORY)))
    except DatabaseError:
        current_app.logger.exception('Cannot load dashboard measurements')
        response = jsonify(error='storage_unavailable')
        response.status_code = 503
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.route('/dashboard/<int:smon_id>/<int:check_id>')
@jwt_required()
@get_user_params()
@feature_required(MONITORING_HISTORY)
def smon_dashboard(smon_id, check_id):
    from flask import abort
    from peewee import DoesNotExist
    from app.modules.tools.check_detail import load_check

    if not roxywi_common.check_user_group_for_flask():
        abort(403)
    group_id = g.user_params['group_id']
    try:
        multi_check, _ = load_check(smon_id, check_id, group_id)
    except DoesNotExist:
        abort(404)
    kwargs = {'lang': g.user_params['lang'], 'group': group_id,
              'smon_name': multi_check.name or '', 'dashboard_id': smon_id, 'check_type_id': check_id}
    for channel, key in (('telegram', 'telegrams'), ('slack', 'slacks'), ('pd', 'pds'),
                         ('incidentrelay', 'incidentrelay'), ('mm', 'mms'), ('email', 'emails')):
        kwargs[key] = channel_sql.get_user_receiver_by_group(channel, group_id)
    return render_template('include/smon/smon_history.html', **kwargs)


@bp.get('/dashboard/<int:smon_id>/<int:check_id>/data')
@jwt_required()
@get_user_params()
@feature_required(MONITORING_HISTORY)
def check_detail_data(smon_id, check_id):
    from flask import current_app
    from peewee import DatabaseError, DoesNotExist
    from app.modules.db.db_model import UserGroups
    from app.modules.tools.check_detail import MetricsUnavailable, snapshot

    user = g.user_params
    if not UserGroups.select().where((UserGroups.user_id == user['user_id']) &
                                     (UserGroups.user_group_id == user['group_id'])).exists():
        return jsonify(error='group_denied'), 403
    try:
        hours = int(request.args.get('hours', '1'))
        location_id = int(request.args['location']) if 'location' in request.args else None
        if hours not in (1, 6, 24) or location_id is not None and location_id <= 0:
            raise ValueError()
    except ValueError:
        return jsonify(error='invalid_query'), 422
    try:
        response = jsonify(snapshot(smon_id, check_id, user['group_id'], hours=hours, location_id=location_id))
    except DoesNotExist:
        return jsonify(error='check_not_found'), 404
    except MetricsUnavailable:
        current_app.logger.warning('Cannot load check metrics', extra={'check_id': smon_id})
        return jsonify(error='metrics_unavailable'), 503
    except DatabaseError:
        current_app.logger.exception('Cannot load check details')
        return jsonify(error='storage_unavailable'), 503
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.route('/status-page', methods=['GET'])
@jwt_required()
@get_user_params()
@feature_required(STATUS_PAGES)
def status_page():
    kwargs = {
        'lang': g.user_params['lang'],
        'smon': smon_sql.select_multi_checks(g.user_params['group_id']),
        'pages': smon_sql.select_status_pages(g.user_params['group_id']),
        'smon_status': tools_common.is_tool_active('rmon-server'),
        'user_subscription': roxywi_common.return_user_subscription()
    }

    return render_template('smon/manage_status_page.html', **kwargs)


@bp.route('/status/<slug>')
@validate()
def show_smon_status_page(slug: EscapedString):
    return smon_mod.show_status_page(slug)


@bp.route('/status/avg/<int:page_id>')
def smon_history_statuses_avg(page_id):
    return smon_mod.avg_status_page_status(page_id)


@bp.route('/history')
@jwt_required()
@get_user_params()
@feature_required(ALERT_HISTORY)
def smon_history():
    roxywi_common.check_user_group_for_flask()

    kwargs = {
        'lang': g.user_params['lang'],
        'smon_status': tools_common.is_tool_active('rmon-server'),
        'user_subscription': roxywi_common.return_user_subscription(),
        'action': 'smon'
    }

    return render_template('smon/history.html', **kwargs)


@bp.route('/history/host/<int:check_id>')
@jwt_required()
@get_user_params()
@feature_required(ALERT_HISTORY)
def smon_host_history(check_id):
    roxywi_common.check_user_group_for_flask()
    smon_status = tools_common.is_tool_active('rmon-server')
    history = history_sql.all_alerts_history('RMON', g.user_params['group_id'], check_id=check_id)
    user_subscription = roxywi_common.return_user_subscription()
    kwargs = {
        'lang': g.user_params['lang'],
        'history': history,
        'smon_status': smon_status,
        'user_subscription': user_subscription,
        'action': 'smon',
    }

    return render_template('smon/history.html', **kwargs)


@bp.route('/history/check/<int:multi_check_id>')
@jwt_required()
@get_user_params()
@feature_required(ALERT_HISTORY)
def smon_multi_check_history(multi_check_id):
    roxywi_common.check_user_group_for_flask()
    smon_status = tools_common.is_tool_active('rmon-server')
    user_subscription = roxywi_common.return_user_subscription()
    kwargs = {
        'lang': g.user_params['lang'],
        'smon_status': smon_status,
        'user_subscription': user_subscription,
        'action': 'smon',
        'multi_check_id': multi_check_id
    }

    return render_template('smon/history.html', **kwargs)


@bp.route('/history/metrics/stream/<int:check_id>/<int:check_type_id>')
@get_user_params()
@feature_required(MONITORING_HISTORY)
def smon_history_metric_chart(check_id, check_type_id):
    """
    This method generates a streaming event chart for the history of a metric associated with a given check ID and check type ID.
    Optimized to reduce database queries and improve performance.

    Parameters:
    - check_id (int): The ID of the check for which to generate the metric history chart.
    - check_type_id (int): The ID of the check type for the given check.

    Returns:
    - A Flask Response object with the streaming event chart.
    """

    def get_chart_data():
        """
        Return a generator that continuously yields chart data in JSON format for the specified check ID and check type ID.
        Optimized to reduce database queries by using cached functions and combining queries.

        Parameters:
        - check_id (int): The ID of the check.
        - check_type_id (int): The ID of the check type.

        Returns:
        A generator that yields chart data in the format of a JSON string.
        """
        # Default interval in case we can't get it from the database
        interval = 120

        while True:
            try:
                # Get all the data we need in a single iteration
                json_metric = {}

                # Get the latest history record
                chart_metrics = smon_sql.get_history(check_id)

                # Get check details (using cached function)
                smon = smon_sql.select_one_smon(check_id, check_type_id)
                is_enabled = 1

                # Process check details
                for s in smon:
                    json_metric['updated_at'] = common.get_time_zoned_date(s.smon_id.updated_at)
                    json_metric['name'] = str(s.smon_id.multi_check_id.name)
                    interval = s.interval  # Update interval in case it changed
                    is_enabled = s.smon_id.enabled
                    if s.smon_id.ssl_expire_date is not None:
                        json_metric['ssl_expire_date'] = smon_mod.get_ssl_expire_date(s.smon_id.ssl_expire_date)
                    else:
                        json_metric['ssl_expire_date'] = 'N/A'

                # Get uptime and average response time (using cached functions)
                uptime = smon_mod.check_uptime(check_id)
                avg_res_time = smon_mod.get_average_response_time(check_id, check_type_id)

                # Build the response JSON
                json_metric['time'] = common.get_time_zoned_date(chart_metrics.date, '%H:%M:%S')
                json_metric['response_time'] = chart_metrics.response_time
                json_metric['mes'] = str(chart_metrics.mes)
                json_metric['uptime'] = uptime
                json_metric['avg_res_time'] = avg_res_time
                json_metric['interval'] = interval
                json_metric['status'] = int(chart_metrics.status) if is_enabled else 4

                # Add HTTP-specific metrics if applicable
                if check_type_id in (2, 3):  # HTTP or HTTPS check types
                    json_metric['name_lookup'] = str(chart_metrics.name_lookup)
                    json_metric['connect'] = str(chart_metrics.connect)
                    json_metric['app_connect'] = str(chart_metrics.app_connect)

                    if check_type_id != 3 and chart_metrics.redirect is not None:
                        json_metric['pre_transfer'] = str(chart_metrics.pre_transfer)

                        if chart_metrics.redirect:
                            json_metric['redirect'] = '0' if float(chart_metrics.redirect) <= 0 else str(chart_metrics.redirect)

                        json_metric['start_transfer'] = '0' if float(chart_metrics.start_transfer) <= 0 else str(chart_metrics.start_transfer)
                        json_metric['m_download'] = str(chart_metrics.download)
                elif check_type_id == 4:
                    json_metric['avg_resp_time'] = str(chart_metrics.name_lookup)
                    json_metric['max_resp_time'] = str(chart_metrics.connect)
                    json_metric['min_resp_time'] = str(chart_metrics.app_connect)
                    json_metric['packet_loss_percent'] = str(chart_metrics.pre_transfer)

                # Send the data
                yield f"data:{json.dumps(json_metric)}\n\n"

            except Exception as e:
                # Log the error but continue the loop
                print(f"Error in chart data generation: {e}")
                # Send minimal data to avoid breaking the client
                yield f"data:{json.dumps({'error': str(e), 'interval': interval})}\n\n"

            # Clean up to prevent memory leaks
            if 'chart_metrics' in locals():
                del chart_metrics
            if 'smon' in locals():
                del smon

            # Sleep for the interval duration
            time.sleep(interval)

    response = Response(stream_with_context(get_chart_data()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response
