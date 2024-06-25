from flask import Blueprint

bp = Blueprint('api_server', __name__)

from app.api.v1.routes.server import routes
