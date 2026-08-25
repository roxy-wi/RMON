from flask import jsonify, request
from peewee import IntegrityError
from pydantic import ValidationError

from app.routes.admin import bp
from app.modules.db import oidc as oidc_sql
from app.modules.oidc.schemas import OidcGroupMappingRequest, OidcProviderCreate, OidcProviderUpdate
from app.modules.subscription.access import OIDC, require_feature
import app.modules.roxywi.auth as roxywi_auth
import app.modules.roxywi.common as roxywi_common
from app.modules.roxywi.exception import (
    RoxywiPermissionError,
    RoxywiResourceNotFound,
    RoxywiValidationError,
)
from app.routes.oidc.routes import _public_oidc_url


def _require_superadmin() -> None:
    require_feature(OIDC)
    if not roxywi_auth.is_admin(level=1):
        raise RoxywiPermissionError('Only super administrators can manage OIDC providers')


def _validation_error(exc: ValidationError):
    errors = [
        {
            'field': '.'.join(str(part) for part in error['loc']),
            'message': error['msg'],
        }
        for error in exc.errors()
    ]
    return jsonify({'status': 'failed', 'error': 'validation_error', 'details': errors}), 400


def _serialize_provider(provider):
    data = oidc_sql.serialize_provider(provider)
    data['callback_url'] = _public_oidc_url(provider.slug)
    return data


def _validate_enabled_provider(data: dict, existing=None) -> None:
    def value(name):
        if name in data:
            return data[name]
        return getattr(existing, name, None) if existing else None

    if not value('enabled'):
        return
    if not value('client_id'):
        raise RoxywiValidationError('An enabled OIDC provider requires client_id')
    if value('metadata_url'):
        return
    required = ('issuer', 'authorization_endpoint', 'token_endpoint', 'jwks_uri')
    missing = [field for field in required if not value(field)]
    if missing:
        raise RoxywiValidationError(
            'An enabled OIDC provider requires metadata_url or these fields: '
            + ', '.join(missing)
        )


@bp.get('/oidc/providers')
def list_oidc_providers():
    _require_superadmin()
    return jsonify([_serialize_provider(provider) for provider in oidc_sql.list_providers()])


@bp.post('/oidc/providers')
def create_oidc_provider():
    _require_superadmin()
    try:
        body = OidcProviderCreate.model_validate(request.get_json(silent=True) or {})
        data = body.model_dump()
        _validate_enabled_provider(data)
        provider = oidc_sql.create_provider(data)
    except ValidationError as exc:
        return _validation_error(exc)
    except RoxywiValidationError as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 400
    except IntegrityError:
        return jsonify({
            'status': 'failed',
            'error': 'An OIDC provider with this slug already exists',
        }), 409

    roxywi_common.logger(
        f'OIDC provider {provider.slug} has been created',
        service='RMON',
        keep_history=1,
    )
    return jsonify(_serialize_provider(provider)), 201


@bp.put('/oidc/providers/<int:provider_id>')
def update_oidc_provider(provider_id: int):
    _require_superadmin()
    try:
        provider = oidc_sql.get_provider(provider_id)
        body = OidcProviderUpdate.model_validate(request.get_json(silent=True) or {})
        data = body.model_dump(exclude_unset=True)
        if data.get('client_secret') == '':
            data.pop('client_secret')
        _validate_enabled_provider(data, existing=provider)
        provider = oidc_sql.update_provider(provider_id, data)
    except ValidationError as exc:
        return _validation_error(exc)
    except RoxywiResourceNotFound as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 404
    except RoxywiValidationError as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 400
    except IntegrityError:
        return jsonify({
            'status': 'failed',
            'error': 'An OIDC provider with this slug already exists',
        }), 409

    roxywi_common.logger(
        f'OIDC provider {provider.slug} has been updated',
        service='RMON',
        keep_history=1,
    )
    return jsonify(_serialize_provider(provider))


@bp.get('/oidc/providers/<int:provider_id>/mappings')
def list_oidc_mappings(provider_id: int):
    _require_superadmin()
    try:
        oidc_sql.get_provider(provider_id)
    except RoxywiResourceNotFound as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 404
    return jsonify([
        oidc_sql.serialize_mapping(mapping)
        for mapping in oidc_sql.list_mappings(provider_id)
    ])


@bp.post('/oidc/providers/<int:provider_id>/mappings')
def create_oidc_mapping(provider_id: int):
    _require_superadmin()
    try:
        body = OidcGroupMappingRequest.model_validate(request.get_json(silent=True) or {})
        mapping = oidc_sql.create_mapping(provider_id, body.model_dump())
    except ValidationError as exc:
        return _validation_error(exc)
    except RoxywiResourceNotFound as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 404
    except RoxywiValidationError as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 400
    except IntegrityError:
        return jsonify({
            'status': 'failed',
            'error': 'This OIDC group mapping already exists',
        }), 409
    return jsonify(oidc_sql.serialize_mapping(mapping)), 201


@bp.put('/oidc/mappings/<int:mapping_id>')
def update_oidc_mapping(mapping_id: int):
    _require_superadmin()
    try:
        body = OidcGroupMappingRequest.model_validate(request.get_json(silent=True) or {})
        mapping = oidc_sql.update_mapping(mapping_id, body.model_dump())
    except ValidationError as exc:
        return _validation_error(exc)
    except RoxywiResourceNotFound as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 404
    except RoxywiValidationError as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 400
    except IntegrityError:
        return jsonify({
            'status': 'failed',
            'error': 'This OIDC group mapping already exists',
        }), 409
    return jsonify(oidc_sql.serialize_mapping(mapping))


@bp.delete('/oidc/mappings/<int:mapping_id>')
def delete_oidc_mapping(mapping_id: int):
    _require_superadmin()
    try:
        oidc_sql.delete_mapping(mapping_id)
    except RoxywiResourceNotFound as exc:
        return jsonify({'status': 'failed', 'error': str(exc)}), 404
    return jsonify({'status': 'Ok'})
