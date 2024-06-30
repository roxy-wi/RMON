from app.api.v1.routes.user import bp
from app.views.user.views import UserView, UserGroupView


def register_api(view, endpoint, url, pk='check_id', pk_type='int'):
    view_func = view.as_view(endpoint, True)
    # bp.add_url_rule(url, defaults={pk: None}, view_func=view_func, methods=['GET',])
    bp.add_url_rule(url, view_func=view_func, methods=['POST',])
    bp.add_url_rule(f'/{url}/<{pk_type}:{pk}>', view_func=view_func, methods=['GET', 'PUT', 'DELETE'])


# bp.add_url_rule('', view_func=UserView.as_view('user', True))
# bp.add_url_rule('/group', view_func=UserGroupView.as_view('user_group', True))

register_api(UserView, 'user', '', 'user_id')
register_api(UserGroupView, 'user_group', '/group', 'group_id')
