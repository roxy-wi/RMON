from app.api.v1.routes.user import bp
from app.views.user.views import UserView


bp.add_url_rule('', view_func=UserView.as_view('user', True))
