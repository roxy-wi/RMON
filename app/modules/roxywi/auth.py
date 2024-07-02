import uuid

from flask import request, abort, url_for, jsonify
from flask_jwt_extended import create_access_token, set_access_cookies
from flask_jwt_extended import get_jwt
from flask_jwt_extended import verify_jwt_in_request

import app.modules.db.sql as sql
import app.modules.db.user as user_sql
import app.modules.db.group as group_sql
import app.modules.roxywi.common as roxywi_common
import app.modules.roxy_wi_tools as roxy_wi_tools


def check_login(user_uuid) -> str:
    if user_uuid is None:
        return 'login_page'

    if user_uuid is not None:
        if user_sql.get_user_name_by_uuid(user_uuid) is None:
            return 'login_page'
        else:
            try:
                ip = request.remote_addr
            except Exception:
                ip = ''

            user_sql.update_last_act_user(user_uuid, ip)

            return 'ok'
    return 'login_page'


def is_admin(level=1, **kwargs):
    if kwargs.get('role_id'):
        role = kwargs.get('role_id')
    else:
        verify_jwt_in_request()
        claims = get_jwt()
        user_id = claims['uuid']
        group_id = claims['group']

        try:
            role = user_sql.get_user_role_by_uuid(user_id, group_id)
        except Exception:
            role = 4
    try:
        return True if int(role) <= int(level) else False
    except Exception:
        return False


def page_for_admin(level=1) -> None:
    if not is_admin(level=level):
        return abort(400, 'bad permission')


def check_in_ldap(user, password):
    import ldap

    server = sql.get_setting('ldap_server')
    port = sql.get_setting('ldap_port')
    ldap_class_search = sql.get_setting('ldap_class_search')
    root_user = sql.get_setting('ldap_user')
    root_password = sql.get_setting('ldap_password')
    ldap_base = sql.get_setting('ldap_base')
    ldap_search_field = sql.get_setting('ldap_search_field')
    ldap_user_attribute = sql.get_setting('ldap_user_attribute')
    ldap_type = sql.get_setting('ldap_type')

    ldap_proto = 'ldap' if ldap_type == "0" else 'ldaps'

    ldap_bind = ldap.initialize('{}://{}:{}/'.format(ldap_proto, server, port))
    try:
        ldap_bind.protocol_version = ldap.VERSION3
        ldap_bind.set_option(ldap.OPT_REFERRALS, 0)

        _ = ldap_bind.simple_bind_s(root_user, root_password)

        criteria = "(&(objectClass=" + ldap_class_search + ")(" + ldap_user_attribute + "=" + user + "))"
        attributes = [ldap_search_field]
        result = ldap_bind.search_s(ldap_base, ldap.SCOPE_SUBTREE, criteria, attributes)

        _ = ldap_bind.simple_bind_s(result[0][0], password)
    except ldap.INVALID_CREDENTIALS:
        return False
    except ldap.SERVER_DOWN:
        raise Exception('error: LDAP server is down')
    except ldap.LDAPError as e:
        if isinstance(e.message, dict) and 'desc' in e.message:
            raise Exception(f'error: {e.message["desc"]}')
        else:
            raise Exception(f'error: {e}')
    else:
        return True


def create_uuid(login: str):
    user_uuid = str(uuid.uuid4())
    user_sql.write_user_uuid(login, user_uuid)

    return user_uuid


def do_login(user_params: dict, next_url: str):
    if next_url:
        redirect_to = f'https://{request.host}{next_url}'
    else:
        redirect_to = f"https://{request.host}{url_for('overview.index')}"

    response = jsonify({"status": "done", "next_url": redirect_to})
    access_token = create_jwt_token(user_params)
    set_access_cookies(response, access_token)

    try:
        user_group_name = group_sql.get_group_name_by_id(user_params['group'])
    except Exception:
        user_group_name = ''

    try:
        user_name = user_sql.get_user_name_by_uuid(user_params['uuid'])
        roxywi_common.logging('RMON server', f' user: {user_name}, group: {user_group_name} login', roxywi=1)
    except Exception as e:
        print(f'error: {e}')

    return response


def create_jwt_token(user_params: dict) -> str:
    additional_claims = {'uuid': user_params['uuid'], 'group': str(user_params['group'])}
    return create_access_token(str(user_params['user']), additional_claims=additional_claims)


def check_user_password(login: str, password: str) -> dict:
    if not login and not password:
        raise Exception('There is no login or password')

    try:
        from playhouse.shortcuts import model_to_dict
        user = user_sql.get_user_by_username(login)
        print(model_to_dict(user))
    except Exception:
        raise Exception('ban')

    if user.enabled == 0:
        raise Exception('Your login is disabled')
    if user.ldap_user == 1:
        if login in user.username and check_in_ldap(login, password):
            user_uuid = create_uuid(login)
            return {'uuid': user_uuid, 'group': str(user.group_id.group_id), 'user': user.user_id}
        else:
            raise Exception('ban')
    else:
        hashed_password = roxy_wi_tools.Tools.get_hash(password)
        if login in user.username and hashed_password == user.password:
            user_uuid = create_uuid(login)
            return {'uuid': user_uuid, 'group': str(user.group_id.group_id), 'user': user.user_id}
        else:
            raise Exception('ban')
