from app.api.v1.routes.user import bp
from app.views.user.views import UserView, UserGroupView, UsersView


def register_api(view, endpoint, url, pk='check_id', pk_type='int'):
    view_func = view.as_view(endpoint, True)
    bp.add_url_rule(url, view_func=view_func, methods=['POST',])
    bp.add_url_rule(f'/{url}/<{pk_type}:{pk}>', view_func=view_func, methods=['GET', 'PUT', 'DELETE'])


def register_api_with_group(view, endpoint, url_beg, url_end, pk='user_id', pk_type='int', pk_end='group_id', pk_type_end='int'):
    view_func = view.as_view(endpoint, True)
    bp.add_url_rule(f'/<{pk_type}:{pk}>/{url_end}', view_func=view_func, methods=['GET'])
    bp.add_url_rule(f'/<{pk_type}:{pk}>/{url_end}/<{pk_type_end}:{pk_end}>', view_func=view_func, methods=['PUT', 'DELETE', 'POST'])


register_api(UserView, 'user', '', 'user_id')
register_api_with_group(UserGroupView, 'user_group', 'user', 'groups')
