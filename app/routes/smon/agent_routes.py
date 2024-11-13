import json

from flask import render_template, request, jsonify, g
from flask_jwt_extended import jwt_required

from app.routes.smon import bp
from app.middleware import get_user_params
import app.modules.db.smon as smon_sql
import app.modules.db.region as region_sql
import app.modules.db.country as country_sql
import app.modules.db.server as server_sql
import app.modules.common.common as common
import app.modules.tools.smon_agent as smon_agent
import app.modules.tools.common as tools_common
import app.modules.roxywi.common as roxywi_common
import app.modules.server.server as server_mod


@bp.route('/agent')
@jwt_required()
@get_user_params()
def agent():
    group_id = g.user_params['group_id']
    kwargs = {
        'countries': country_sql.select_countries_by_group(group_id),
        'regions': region_sql.select_regions_by_group(group_id),
        'agents': smon_sql.get_agents(group_id),
        'lang': roxywi_common.get_user_lang_for_flask(),
        'smon_status': tools_common.is_tool_active('rmon-server'),
    }

    return render_template('smon/agents.html', **kwargs)


@bp.get('/agent/<int:agent_id>')
@jwt_required()
@get_user_params()
def get_agent(agent_id):
    kwargs = {
        'agents': smon_sql.get_agent(agent_id),
        'lang': roxywi_common.get_user_lang_for_flask(),
        'smon_status': tools_common.is_tool_active('rmon-server'),
    }

    for check_type in ('http', 'tcp', 'dns', 'ping', 'smtp', 'rabbitmq'):
        kwargs[f'{check_type}_checks'] = smon_sql.select_checks_for_agent_by_check_type(agent_id, check_type)

    return render_template('smon/agent.html', **kwargs)


@bp.post('/agent/hello')
def agent_get_checks():
    json_data = request.json
    agent_id = smon_sql.get_agent_by_uuid(json_data['uuid'])
    try:
        smon_agent.send_checks(agent_id.id)
    except Exception as e:
        return f'{e}'
    return 'ok'


@bp.get('/agent/free')
@jwt_required()
@get_user_params()
def get_free_agents():
    group_id = g.user_params['group_id']
    free_servers = smon_sql.get_free_servers_for_agent(group_id)
    servers = {}
    for s in free_servers:
        servers.setdefault(s.server_id, s.hostname)

    return jsonify(servers)


@bp.get('/agent/count')
@jwt_required()
def get_agent_count():
    try:
        smon_agent.check_agent_limit()
    except Exception as e:
        return f'{e}'

    return 'ok'


@bp.get('/agent/info/<int:agent_id>')
@jwt_required()
@get_user_params()
def get_agent_info(agent_id):
    try:
        agent_data = smon_sql.get_agent(agent_id)
    except Exception as e:
        return f'{e}'

    return render_template('ajax/smon/agent.html', agents=agent_data, lang=roxywi_common.get_user_lang_for_flask())


@bp.get('/region/info/<int:region_id>')
@jwt_required()
@get_user_params()
def get_region_info(region_id):
    try:
        region_data = region_sql.get_region_with_group(region_id, g.user_params['group_id'])
        agents = smon_sql.get_agents_by_region(region_id)
    except Exception as e:
        return f'{e}'

    return render_template('ajax/smon/region.html', region=region_data, agents=agents, lang=roxywi_common.get_user_lang_for_flask())


@bp.get('/country/info/<int:country_id>')
@jwt_required()
@get_user_params()
def get_country_info(country_id):
    try:
        country_data = country_sql.get_country_with_group(country_id, g.user_params['group_id'])
        regions = region_sql.get_regions_by_country(country_id)
    except Exception as e:
        return f'{e}'

    return render_template('ajax/smon/country.html', country=country_data, regions=regions, lang=roxywi_common.get_user_lang_for_flask())


@bp.get('/agent/version/<server_ip>')
@jwt_required()
def get_agent_version(server_ip):
    agent_id = int(request.args.get('agent_id'))
    last_agent_version = '0.2'

    try:
        req = smon_agent.send_get_request_to_agent(agent_id, server_ip, 'version')
        j_resp = json.loads(req)
        if float(j_resp['version']) < float(last_agent_version):
            j_resp['update'] = "1"
        return jsonify(j_resp)
    except Exception as e:
        return f'{e}'


@bp.get('/agent/uptime/<server_ip>')
@jwt_required()
def get_agent_uptime(server_ip):
    agent_id = int(request.args.get('agent_id'))

    try:
        req = smon_agent.send_get_request_to_agent(agent_id, server_ip, 'uptime')
        return req
    except Exception as e:
        return f'{e}'


@bp.get('/agent/status/<server_ip>')
@jwt_required()
def get_agent_status(server_ip):
    agent_id = int(request.args.get('agent_id'))

    try:
        req = smon_agent.send_get_request_to_agent(agent_id, server_ip, 'scheduler')
        return req
    except Exception as e:
        return f'{e}'


@bp.get('/agent/checks/<server_ip>')
@jwt_required()
def get_agent_checks(server_ip):
    agent_id = int(request.args.get('agent_id'))

    try:
        req = smon_agent.send_get_request_to_agent(agent_id, server_ip, 'checks')
        return req
    except Exception as e:
        return f'{e}'


@bp.post('/agent/action/<action>')
@jwt_required()
@get_user_params()
def agent_action(action):
    server_ip = common.is_ip_or_dns(request.form.get('server_ip'))
    server_group_id = server_sql.get_server_group(server_ip)

    if action not in ('start', 'stop', 'restart'):
        return 'error: Wrong action'

    if g.user_params['group_id'] != server_group_id and g.user_params['role'] > 1:
        return 'error: Not authorized'

    try:
        command = f'sudo systemctl {action} rmon-agent'
        server_mod.ssh_command(server_ip, command, timeout=30)
    except Exception as e:
        return f'{e}'
    return 'ok'
