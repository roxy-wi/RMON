from flask import request, render_template, g, jsonify
from flask_jwt_extended import jwt_required

from app.routes.channel import bp
from app.middleware import get_user_params
import app.modules.common.common as common
import app.modules.tools.alerting as alerting
import app.modules.roxywi.common as roxywi_common
from app.views.channel.views import ChannelView

bp.add_url_rule(f'/channel/<any(telegram, slack, pd, mm):receiver>', view_func=ChannelView.as_view('channel', False), methods=['POST'])


@bp.before_request
@jwt_required()
def before_request():
    """ Protect all the admin endpoints. """
    pass


@bp.route('')
@get_user_params()
def channels():
    roxywi_common.check_user_group_for_flask()
    lang = g.user_params['lang']

    return render_template('channel.html', lang=lang)


@bp.route('/load')
@get_user_params()
def load_channels():
    try:
        return alerting.load_channels()
    except Exception as e:
        return f'{e}'


@bp.route('/check/<int:channel_id>/<receiver_name>')
def check_receiver(channel_id, receiver_name):
    receiver_name = common.checkAjaxInput(receiver_name)

    try:
        alerting.check_receiver(channel_id, receiver_name)
        return jsonify({'status': 'success'})
    except Exception as e:
        return roxywi_common.handle_json_exceptions(e, f'Cannot send message via {receiver_name}')


@bp.post('/check')
@get_user_params()
def check_sender():
    json_data = request.get_json()
    sender = json_data.get('sender')
    send_function = {
        'email': alerting.check_email_alert,
        'web': alerting.check_rabbit_alert
    }
    try:
        send_function[sender]()
        return jsonify({'status': 'success'})
    except Exception as e:
        return roxywi_common.handle_json_exceptions(e, f'Cannot send message via {sender.title()}')
