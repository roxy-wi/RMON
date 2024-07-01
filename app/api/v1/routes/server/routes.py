from app.api.v1.routes.server import bp
from app.views.server.views import ServerView, CredsView


bp.add_url_rule('', view_func=ServerView.as_view('server', True))
bp.add_url_rule('/cred', view_func=CredsView.as_view('cred', True))
