from flask import Blueprint


bp = Blueprint('oidc', __name__)


from app.routes.oidc import routes
