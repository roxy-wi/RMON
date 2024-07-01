from app.api.v1.routes.rmon import bp
from app.views.agent.views import AgentView, AgentsView
from app.views.check.views import CheckHttpView, CheckTcpView, CheckDnsView, CheckPingView


def register_api(view, endpoint, url, pk='check_id', pk_type='int'):
    view_func = view.as_view(endpoint)
    # bp.add_url_rule(url, defaults={pk: None}, view_func=view_func, methods=['GET',])
    bp.add_url_rule(url, view_func=view_func, methods=['POST',])
    bp.add_url_rule(f'/{url}/<{pk_type}:{pk}>', view_func=view_func, methods=['GET', 'PUT', 'DELETE'])


# bp.add_url_rule('/agent', view_func=AgentView.as_view('agent', True))
bp.add_url_rule('/agents', view_func=AgentsView.as_view('agents', True))

register_api(AgentView, 'agent', '/agent', 'agent_id')
register_api(CheckHttpView, 'http_check', '/check/http', 'check_id')
register_api(CheckTcpView, 'tcp_check', '/check/tcp', 'check_id')
register_api(CheckPingView, 'ping_check', '/check/ping', 'check_id')
register_api(CheckDnsView, 'dns_check', '/check/dns', 'check_id')
