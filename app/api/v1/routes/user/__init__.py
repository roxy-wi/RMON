from flask import Blueprint

bp = Blueprint('api_user', __name__)

from app.api.v1.routes.user import routes
