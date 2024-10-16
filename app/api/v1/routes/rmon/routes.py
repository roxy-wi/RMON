from app.api.v1.routes.rmon import bp
from app.views.agent.views import AgentView, AgentsView
from app.views.agent.region_views import RegionView, RegionListView
from app.views.agent.country_views import CountryView, CountryListView
from app.views.check.views import CheckHttpView, CheckTcpView, CheckDnsView, CheckPingView, CheckSmtpView, CheckRabbitView
from app.views.check.checks_view import ChecksViewHttp, ChecksViewDns, ChecksViewTcp, ChecksViewPing, ChecksViewSmtp, ChecksViewRabbit
from app.views.check.check_metric_view import (ChecksMetricViewHttp, ChecksMetricViewTcp, ChecksMetricViewDNS,
                                               ChecksMetricViewPing, ChecksMetricViewSMTP, ChecksMetricViewRabbitmq,
                                               CheckStatusesView, CheckStatusView)
from app.views.check.status_page_views import StatusPageView


def register_api(view, endpoint, url, pk='check_id', pk_type='int'):
    view_func = view.as_view(endpoint)
    bp.add_url_rule(url, view_func=view_func, methods=['POST',])
    bp.add_url_rule(f'/{url}/<{pk_type}:{pk}>', view_func=view_func, methods=['GET', 'PUT', 'DELETE'])


bp.add_url_rule('/agents', view_func=AgentsView.as_view('agents'))
bp.add_url_rule('/regions', view_func=RegionListView.as_view('regions'))
bp.add_url_rule('/countries', view_func=CountryListView.as_view('countries'))
bp.add_url_rule('/checks/http', view_func=ChecksViewHttp.as_view('http_checks'))
bp.add_url_rule('/checks/dns', view_func=ChecksViewDns.as_view('dns_checks'))
bp.add_url_rule('/checks/tcp', view_func=ChecksViewTcp.as_view('tcp_checks'))
bp.add_url_rule('/checks/ping', view_func=ChecksViewPing.as_view('ping_checks'))
bp.add_url_rule('/checks/smtp', view_func=ChecksViewSmtp.as_view('smtp_checks'))
bp.add_url_rule('/checks/rabbitmq', view_func=ChecksViewRabbit.as_view('rabbit_checks'))
bp.add_url_rule('/check/http/<int:check_id>/metrics', view_func=ChecksMetricViewHttp.as_view('http_metric'))
bp.add_url_rule('/check/tcp/<int:check_id>/metrics', view_func=ChecksMetricViewTcp.as_view('tcp_metric'))
bp.add_url_rule('/check/dns/<int:check_id>/metrics', view_func=ChecksMetricViewDNS.as_view('dns_metric'))
bp.add_url_rule('/check/ping/<int:check_id>/metrics', view_func=ChecksMetricViewPing.as_view('ping_metric'))
bp.add_url_rule('/check/smtp/<int:check_id>/metrics', view_func=ChecksMetricViewSMTP.as_view('smtp_metric'))
bp.add_url_rule('/check/rabbitmq/<int:check_id>/metrics', view_func=ChecksMetricViewRabbitmq.as_view('rabbitmq_metric'))
bp.add_url_rule('/check/<int:check_id>/statuses', view_func=CheckStatusesView.as_view('check_statuses'))
bp.add_url_rule('/check/<int:check_id>/status', view_func=CheckStatusView.as_view('check_status'))

register_api(AgentView, 'agent', '/agent', 'agent_id')
register_api(RegionView, 'region', '/region', 'region_id')
register_api(CountryView, 'country', '/country', 'country_id')
register_api(CheckHttpView, 'http_check', '/check/http', 'check_id')
register_api(CheckTcpView, 'tcp_check', '/check/tcp', 'check_id')
register_api(CheckPingView, 'ping_check', '/check/ping', 'check_id')
register_api(CheckDnsView, 'dns_check', '/check/dns', 'check_id')
register_api(CheckSmtpView, 'smtp_check', '/check/smtp', 'check_id')
register_api(CheckRabbitView, 'rabbit_check', '/check/rabbitmq', 'check_id')
register_api(StatusPageView, 'status_page', '/status-page', 'page_id')
