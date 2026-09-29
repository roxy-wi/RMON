"""Strict JSON parsing and safe errors for the authenticated management API."""
import json
import logging

from flask import jsonify, request
from peewee import DatabaseError
from pydantic import ValidationError
from werkzeug.exceptions import RequestEntityTooLarge

from app.modules.client_telemetry.schemas import MAX_BATCH_BYTES
from app.modules.client_telemetry.service import TelemetryError

logger = logging.getLogger(__name__)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError('Non-finite JSON number')


def _portable_strings(value):
    # PostgreSQL JSONB cannot represent NUL or lone Unicode surrogates. Reject
    # them uniformly instead of accepting different data on different engines.
    if isinstance(value, str):
        if '\x00' in value:
            raise ValueError('NUL is not supported')
        value.encode('utf-8', errors='strict')
    elif isinstance(value, dict):
        for key, item in value.items():
            _portable_strings(key)
            _portable_strings(item)
    elif isinstance(value, list):
        for item in value:
            _portable_strings(item)


def read_body(schema):
    if request.content_encoding not in (None, 'identity'):
        raise TelemetryError(415, 'unsupported_encoding', 'Send an uncompressed JSON body')
    if request.mimetype != 'application/json' or request.mimetype_params.get('charset', 'utf-8').lower() != 'utf-8':
        raise TelemetryError(415, 'unsupported_media_type', 'Send JSON encoded as UTF-8')
    if request.content_length is not None and request.content_length > MAX_BATCH_BYTES:
        raise RequestEntityTooLarge()
    raw = request.stream.read(MAX_BATCH_BYTES + 1)
    if len(raw) > MAX_BATCH_BYTES:
        raise RequestEntityTooLarge()
    try:
        body = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=_invalid_number)
        _portable_strings(body)
    except (ValueError, UnicodeError, RecursionError):
        raise TelemetryError(400, 'invalid_json', 'Send UTF-8 JSON with unique fields, finite numbers and no NUL characters') from None
    return schema.model_validate(body)


def register_errors(target):
    @target.errorhandler(TelemetryError)
    def telemetry_error(error):
        body = {'error': error.code, 'message': error.message}
        if error.details:
            body['details'] = error.details
        response = jsonify(body)
        response.status_code = error.status
        if error.retry_after:
            response.headers['Retry-After'] = str(error.retry_after)
        return response

    @target.errorhandler(ValidationError)
    def validation_error(error):
        # Never include Pydantic's input or exception context (they may contain keys).
        details = [{'field': '.'.join(map(str, item['loc'])), 'message': item['msg']}
                   for item in error.errors(include_input=False, include_context=False, include_url=False)]
        return jsonify(error='invalid_payload', message='Correct the indicated fields', details=details), 422

    @target.errorhandler(DatabaseError)
    def database_error(error):
        logger.error('Client telemetry database operation failed (%s)', type(error).__name__)
        return jsonify(error='storage_unavailable', message='Storage is temporarily unavailable; retry later'), 503, {'Retry-After': '5'}

    @target.errorhandler(RequestEntityTooLarge)
    def oversized(error):
        return jsonify(error='payload_too_large', message=f'Limit the JSON body to {MAX_BATCH_BYTES} bytes'), 413
