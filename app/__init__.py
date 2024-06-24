from flask import Flask
from flask_caching import Cache
# from flask_login import LoginManager
from flask_apscheduler import APScheduler
from flask_jwt_extended import JWTManager

app = Flask(__name__)
app.config.from_object('app.config.Configuration')
app.jinja_env.add_extension('jinja2.ext.do')
app.jinja_env.add_extension('jinja2.ext.loopcontrols')

jwt = JWTManager(app)

cache = Cache()
cache.init_app(app)

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()
#
# login_manager = LoginManager(app)
# login_manager.login_view = 'login_page'

from app.api.v1.routes.main import bp as main_api_bp
from app.api.v1.routes.user import bp as user_api_bp

app.register_blueprint(main_api_bp, url_prefix="/api/v1.0")
app.register_blueprint(user_api_bp, url_prefix="/api/v1.0/user")

from app.routes.main import bp as main_bp
from app.routes.smon import bp as smon_bp
from app.routes.channel import bp as channel_bp
from app.routes.user import bp as user_bp
from app.routes.server import bp as server_bp
from app.routes.admin import bp as admin_bp
from app.routes.overview import bp as overview_bp
from app.routes.logs import bp as logs_bp

app.register_blueprint(main_bp)
app.register_blueprint(overview_bp)
app.register_blueprint(smon_bp, url_prefix='/rmon')
app.register_blueprint(channel_bp, url_prefix='/channel')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(logs_bp, url_prefix='/logs')
app.register_blueprint(server_bp, url_prefix='/server')
app.register_blueprint(admin_bp, url_prefix='/admin')

from app import login
from app import jobs
