from app.api.v1.routes.rmon import bp
from app.views.agent.views import AgentView, AgentsView
from app.views.check.views import (
    CheckHttpView, CheckTcpView, CheckDnsView, CheckPingView, ChecksViewHttp, ChecksViewDns, ChecksViewTcp,
    ChecksViewPing, CheckSmtpView, ChecksViewSmtp
)


def register_api(view, endpoint, url, pk='check_id', pk_type='int'):
    view_func = view.as_view(endpoint)
    bp.add_url_rule(url, view_func=view_func, methods=['POST',])
    bp.add_url_rule(f'/{url}/<{pk_type}:{pk}>', view_func=view_func, methods=['GET', 'PUT', 'DELETE'])


bp.add_url_rule('/agents', view_func=AgentsView.as_view('agents'))
bp.add_url_rule('/checks/http', view_func=ChecksViewHttp.as_view('http_checks'))
bp.add_url_rule('/checks/dns', view_func=ChecksViewDns.as_view('dns_checks'))
bp.add_url_rule('/checks/tcp', view_func=ChecksViewTcp.as_view('tcp_checks'))
bp.add_url_rule('/checks/ping', view_func=ChecksViewPing.as_view('ping_checks'))
bp.add_url_rule('/checks/smtp', view_func=ChecksViewSmtp.as_view('smtp_checks'))

register_api(AgentView, 'agent', '/agent', 'agent_id')
register_api(CheckHttpView, 'http_check', '/check/http', 'check_id')
register_api(CheckTcpView, 'tcp_check', '/check/tcp', 'check_id')
register_api(CheckPingView, 'ping_check', '/check/ping', 'check_id')
register_api(CheckDnsView, 'dns_check', '/check/dns', 'check_id')
register_api(CheckSmtpView, 'smtp_check', '/check/smtp', 'check_id')
