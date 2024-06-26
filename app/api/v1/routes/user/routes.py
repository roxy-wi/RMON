from app.api.v1.routes.user import bp
from app.views.user.views import UserView, UserGroupView


bp.add_url_rule('', view_func=UserView.as_view('user', True))
bp.add_url_rule('/group', view_func=UserGroupView.as_view('user_group', True))
