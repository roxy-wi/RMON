import os

from flask import make_response

import app.modules.db.sql as sql
import app.modules.db.user as user_sql
import app.modules.roxywi.common as roxywi_common
import app.modules.tools.alerting as alerting


def create_user(new_user: str, email: str, password: str, role: int, activeuser: int, group: int) -> int:
    try:
        user_id = user_sql.add_user(new_user, email, password, role, activeuser, group)
        roxywi_common.logging(f'a new user {new_user}', 'has been created', login=1)
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'RMON server', 'Cannot create a new user', login=1)
    try:
        user_sql.update_user_role(user_id, group, role)
    except Exception as e:
        raise Exception(f'error: cannot update user role {e}')
    try:
        if not sql.get_setting('mail_enabled') or not sql.get_setting('mail_send_hello_message'):
            return user_id
        if password == 'aduser':
            password = 'your domain password'
        rmon_name = sql.get_setting('rmon_name')
        message = f"A user has been created for you on {rmon_name} portal!\n\n" \
                  f"Now you can login to https://{os.environ.get('HTTP_HOST', '')}\n\n" \
                  f"Your credentials are:\n" \
                  f"Login: {new_user}\n" \
                  f"Password: {password}"
        alerting.send_email(email, 'A user has been created for you', message)
    except Exception as e:
        roxywi_common.logging('error: Cannot send email for a new user', str(e), login=1)

    return user_id


def delete_user(user_id: int) -> None:
    if user_sql.is_user_super_admin(user_id):
        count_super_admin_users = user_sql.get_super_admin_count()
        if count_super_admin_users < 2:
            raise Exception('error: you cannot delete a last user with superAdmin role')
    user = user_sql.select_users(id=user_id)
    username = ''
    for u in user:
        username = u.username
    if user_sql.delete_user(user_id):
        user_sql.delete_user_groups(user_id)
        roxywi_common.logging(username, 'has been deleted user', login=1)


def update_user(email, new_user, user_id, enabled, group_id, role_id):
    try:
        user_sql.update_user(new_user, email, role_id, user_id, enabled)
    except Exception as e:
        roxywi_common.handle_exceptions(e, 'RMON server', f'Cannot update user {new_user}', login=1)
    user_sql.update_user_role(user_id, group_id, role_id)
    roxywi_common.logging(new_user, 'has been updated user', login=1)


def update_user_password(password, user_id):
    user = user_sql.get_user_id(user_id)
    user_sql.update_user_password(password, user_id)
    roxywi_common.logging(f'user {user.username}', 'has changed password', login=1)


def save_user_group_and_role(user: str, groups_and_roles: dict):
    resp = make_response('ok')
    for k, v in groups_and_roles.items():
        user_id = int(k)
        if not user_sql.delete_user_groups(user_id):
            return 'error: Cannot delete old groups'
        for k2, v2 in v.items():
            group_id = int(k2)
            role_id = int(v2['role_id'])
            if len(v) == 1:
                user_sql.update_user_current_groups_by_id(group_id, user_id)
            try:
                user_sql.update_user_role(user_id, group_id, role_id)
            except Exception as e:
                raise Exception(f'error: Cannot update groups: {e}')
        else:
            roxywi_common.logging('RMON server', f'Groups and roles have been updated for user: {user}', login=1)
            return resp


def get_ldap_email(username) -> str:
    import ldap

    server = sql.get_setting('ldap_server')
    port = sql.get_setting('ldap_port')
    user = sql.get_setting('ldap_user')
    password = sql.get_setting('ldap_password')
    ldap_base = sql.get_setting('ldap_base')
    domain = sql.get_setting('ldap_domain')
    ldap_search_field = sql.get_setting('ldap_search_field')
    ldap_class_search = sql.get_setting('ldap_class_search')
    ldap_user_attribute = sql.get_setting('ldap_user_attribute')
    ldap_type = sql.get_setting('ldap_type')
    ldap_proto = 'ldap' if ldap_type == "0" else 'ldaps'

    try:
        ldap_bind = ldap.initialize(f'{ldap_proto}://{server}:{port}/')
    except Exception as e:
        raise Exception(f'Cannot initialize connect to LDAP: {e}')

    try:
        ldap_bind.protocol_version = ldap.VERSION3
        ldap_bind.set_option(ldap.OPT_REFERRALS, 0)
        ldap_bind.simple_bind_s(user, password)

        criteria = f"(&(objectClass={ldap_class_search})({ldap_user_attribute}={username}))"
        attributes = [ldap_search_field]
        result = ldap_bind.search_s(ldap_base, ldap.SCOPE_SUBTREE, criteria, attributes)

        results = [entry for dn, entry in result if isinstance(entry, dict)]
        try:
            return f'["{results[0][ldap_search_field][0].decode("utf-8")}","{domain}"]'
        except Exception:
            raise Exception('user not found')
    except Exception as e:
        raise Exception(e)
    finally:
        ldap_bind.unbind()
