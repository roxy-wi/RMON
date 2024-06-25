from functools import wraps

from flask import redirect, url_for, g, request, jsonify, abort

import app.modules.roxywi.common as roxywi_common
import app.modules.roxywi.auth as roxywi_auth


def get_user_params(virt=0, disable=0):
    def inner_decorator(fn):
        @wraps(fn)
        def decorated_views(*args, **kwargs):
            try:
                user_params = roxywi_common.get_users_params(virt=virt, disable=disable)
                g.user_params = user_params
            except Exception as e:
                print(f'{e}')
                if 'api' in request.url:
                    return jsonify({'error': str(e)})
                else:
                    return redirect(url_for('login_page'))
            return fn(*args, **kwargs)
        return decorated_views
    return inner_decorator


def page_for_admin(level=1):
    def inner_decorator(fn):
        @wraps(fn)
        def decorated_views(*args, **kwargs):
            if not roxywi_auth.is_admin(level=level):
                return abort(400, 'bad permission')
            else:
                return fn(*args, **kwargs)
        return decorated_views
    return inner_decorator
