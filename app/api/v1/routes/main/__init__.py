from flask import Blueprint

bp = Blueprint('api_main', __name__)

from app.api.v1.routes.main import routes
