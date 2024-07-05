from app.api.v1.routes.server import bp
from app.views.server.views import ServerView, CredView, CredsView


def register_api(view, endpoint, url, pk='check_id', pk_type='int'):
    view_func = view.as_view(endpoint, True)
    bp.add_url_rule(url, view_func=view_func, methods=['POST',])
    bp.add_url_rule(f'/{url}/<{pk_type}:{pk}>', view_func=view_func, methods=['GET', 'PUT', 'DELETE', 'PATCH'])


register_api(ServerView, 'server', '', 'server_id')
register_api(CredView, 'cred', '/cred', 'creds_id')
bp.add_url_rule('/creds', view_func=CredsView.as_view('creds'))
