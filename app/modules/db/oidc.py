import json
from datetime import datetime
from typing import Optional

from app.modules.db.db_model import Groups, OidcGroupMapping, OidcIdentity, OidcProvider, Role
from app.modules.roxywi.exception import RoxywiResourceNotFound, RoxywiValidationError


def _allowed_domains_from_db(value: Optional[str]) -> list[str]:
    if not value:
        return []
    try:
        domains = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        domains = str(value).split(',')
    return [str(domain).strip().lower() for domain in domains if str(domain).strip()]


def _allowed_domains_for_db(value) -> str:
    if isinstance(value, str):
        value = value.split(',')
    domains = [str(domain).strip().lower() for domain in (value or []) if str(domain).strip()]
    return json.dumps(domains)


def serialize_provider(provider: OidcProvider) -> dict:
    return {
        'id': provider.id,
        'slug': provider.slug,
        'label': provider.label,
        'enabled': bool(provider.enabled),
        'client_id': provider.client_id,
        'client_secret_configured': bool(provider.client_secret_encrypted),
        'metadata_url': provider.metadata_url,
        'issuer': provider.issuer,
        'authorization_endpoint': provider.authorization_endpoint,
        'token_endpoint': provider.token_endpoint,
        'userinfo_endpoint': provider.userinfo_endpoint,
        'jwks_uri': provider.jwks_uri,
        'scope': provider.scope,
        'subject_claim': provider.subject_claim,
        'email_claim': provider.email_claim,
        'username_claim': provider.username_claim,
        'groups_claim': provider.groups_claim,
        'allowed_domains': _allowed_domains_from_db(provider.allowed_domains),
        'auto_create_users': bool(provider.auto_create_users),
        'auto_link_by_email': bool(provider.auto_link_by_email),
        'require_verified_email': bool(provider.require_verified_email),
        'sync_group_memberships': bool(provider.sync_group_memberships),
        'remove_missing_group_memberships': bool(provider.remove_missing_group_memberships),
        'default_group_id': provider.default_group_id,
        'default_role_id': provider.default_role_id,
    }


def serialize_mapping(mapping: OidcGroupMapping) -> dict:
    group = Groups.get_or_none(Groups.group_id == mapping.group_id)
    role = Role.get_or_none(Role.role_id == mapping.role_id)
    return {
        'id': mapping.id,
        'provider_id': mapping.provider_id,
        'external_group': mapping.external_group,
        'group_id': mapping.group_id,
        'group_name': group.name if group else None,
        'role_id': mapping.role_id,
        'role_name': role.name if role else None,
        'active': bool(mapping.active),
        'priority': mapping.priority,
    }


def list_providers(enabled_only: bool = False):
    query = OidcProvider.select()
    if enabled_only:
        query = query.where(OidcProvider.enabled == 1)
    return query.order_by(OidcProvider.label.asc()).execute()


def get_provider(provider_id: int) -> OidcProvider:
    provider = OidcProvider.get_or_none(OidcProvider.id == provider_id)
    if not provider:
        raise RoxywiResourceNotFound('OIDC provider was not found')
    return provider


def get_provider_by_slug(slug: str, enabled_only: bool = False) -> OidcProvider:
    query = OidcProvider.select().where(OidcProvider.slug == slug)
    if enabled_only:
        query = query.where(OidcProvider.enabled == 1)
    provider = query.get_or_none()
    if not provider:
        raise RoxywiResourceNotFound('OIDC provider was not found or is disabled')
    return provider


def _validate_group_and_role(group_id: int, role_id: int) -> None:
    if not Groups.get_or_none(Groups.group_id == group_id):
        raise RoxywiValidationError('OIDC target group does not exist')
    if not Role.get_or_none(Role.role_id == role_id):
        raise RoxywiValidationError('OIDC target role does not exist')


def _provider_values(data: dict, existing: OidcProvider = None) -> dict:
    values = dict(data)
    client_secret = values.pop('client_secret', None)
    if 'allowed_domains' in values:
        values['allowed_domains'] = _allowed_domains_for_db(values['allowed_domains'])
    if client_secret:
        from app.modules.server.ssh import crypt_password

        values['client_secret_encrypted'] = crypt_password(client_secret).decode('ascii')
    elif existing is None:
        values['client_secret_encrypted'] = None
    values['updated_at'] = datetime.now()
    return values


def create_provider(data: dict) -> OidcProvider:
    _validate_group_and_role(data['default_group_id'], data['default_role_id'])
    values = _provider_values(data)
    values['created_at'] = datetime.now()
    return OidcProvider.create(**values)


def update_provider(provider_id: int, data: dict) -> OidcProvider:
    provider = get_provider(provider_id)
    group_id = data.get('default_group_id', provider.default_group_id)
    role_id = data.get('default_role_id', provider.default_role_id)
    _validate_group_and_role(group_id, role_id)
    for key, value in _provider_values(data, existing=provider).items():
        setattr(provider, key, value)
    provider.save()
    return provider


def list_mappings(provider_id: int, active_only: bool = False):
    query = OidcGroupMapping.select().where(OidcGroupMapping.provider_id == provider_id)
    if active_only:
        query = query.where(OidcGroupMapping.active == 1)
    return query.order_by(OidcGroupMapping.priority.asc(), OidcGroupMapping.id.asc()).execute()


def get_mapping(mapping_id: int) -> OidcGroupMapping:
    mapping = OidcGroupMapping.get_or_none(OidcGroupMapping.id == mapping_id)
    if not mapping:
        raise RoxywiResourceNotFound('OIDC group mapping was not found')
    return mapping


def create_mapping(provider_id: int, data: dict) -> OidcGroupMapping:
    get_provider(provider_id)
    _validate_group_and_role(data['group_id'], data['role_id'])
    return OidcGroupMapping.create(provider_id=provider_id, **data)


def update_mapping(mapping_id: int, data: dict) -> OidcGroupMapping:
    mapping = get_mapping(mapping_id)
    group_id = data.get('group_id', mapping.group_id)
    role_id = data.get('role_id', mapping.role_id)
    _validate_group_and_role(group_id, role_id)
    data['updated_at'] = datetime.now()
    OidcGroupMapping.update(**data).where(OidcGroupMapping.id == mapping_id).execute()
    return get_mapping(mapping_id)


def delete_mapping(mapping_id: int) -> None:
    get_mapping(mapping_id).delete_instance()


def delete_identities_for_user(user_id: int) -> None:
    OidcIdentity.delete().where(OidcIdentity.user_id == user_id).execute()
