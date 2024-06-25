from app.api.v1.routes.server import bp
from app.views.server.views import ServerView, GroupView


bp.add_url_rule('', view_func=ServerView.as_view('server', True))
bp.add_url_rule('/group', view_func=GroupView.as_view('group', True))
