from flask import Blueprint

bp = Blueprint('client', __name__)

from app.api.v1.routes.client import routes
