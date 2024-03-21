from flask import render_template, g, request, jsonify
from flask_login import login_required

from app.routes.overview import bp
from app.middleware import get_user_params
import app.modules.db.sql as sql
import app.modules.db.group as group_sql
import app.modules.roxywi.logs as roxy_logs
import app.modules.roxywi.metrics as metric
import app.modules.roxywi.overview as roxy_overview
import app.modules.common.common as common


@bp.before_request
@login_required
def before_request():
    """ Protect all the admin endpoints. """
    pass


@bp.route('/')
@bp.route('/overview')
@get_user_params()
def index():
    kwargs = {
        'autorefresh': 1,
        'roles': sql.select_roles(),
        'groups': group_sql.select_groups(),
        'lang': g.user_params['lang']
    }
    return render_template('ovw.html', **kwargs)


@bp.route('/overview/services')
def show_services_overview():
    return roxy_overview.show_services_overview()


@bp.route('/overview/server/<server_ip>')
def overview_server(server_ip):
    return roxy_overview.show_overview(server_ip)


@bp.route('/overview/users')
def overview_users():
    return roxy_overview.user_owv()


@bp.route('/overview/sub')
def overview_sub():
    return roxy_overview.show_sub_ovw()


@bp.route('/overview/logs')
@get_user_params()
def overview_logs():
    return render_template('ajax/ovw_log.html', role=g.user_params['role'], lang=g.user_params['lang'], roxy_wi_log=roxy_logs.roxy_wi_log())


@bp.route('/metrics/cpu', methods=['POST'])
def metrics_cpu():
    metrics_type = common.checkAjaxInput(request.form.get('ip'))

    return jsonify(metric.show_cpu_metrics(metrics_type))


@bp.route('/metrics/ram', methods=['POST'])
def metrics_ram():
    metrics_type = common.checkAjaxInput(request.form.get('ip'))

    return jsonify(metric.show_ram_metrics(metrics_type))