"""
Error handling module for RMON.

This module provides a unified way to handle errors across the application.
It includes functions for handling exceptions, logging errors, and returning
appropriate HTTP responses.
"""

from typing import Any, Dict, Tuple

from flask import jsonify, request, render_template, g, redirect, url_for, has_request_context
from werkzeug.exceptions import HTTPException
from flask_pydantic.exceptions import ValidationError

from app.modules.roxywi.class_models import ErrorResponse
from app.modules.roxywi.exception import (
    RoxywiResourceNotFound,
    RoxywiGroupMismatch,
    RoxywiGroupNotFound,
    RoxywiPermissionError,
    RoxywiConflictError,
    RoxywiValidationError,
    RoxywiCheckLimits
)
from app.middleware import get_user_params
from app.modules.roxywi.logger import log_level

# Map exception types to HTTP status codes
ERROR_CODE_MAPPING = {
    RoxywiResourceNotFound: 404,
    RoxywiGroupNotFound: 404,
    RoxywiGroupMismatch: 404,
    RoxywiPermissionError: 403,
    RoxywiConflictError: 409,
    RoxywiValidationError: 400,
    RoxywiCheckLimits: 402,
    KeyError: 400,
    ValueError: 400,
    Exception: 500
}

# Map exception types to error messages
ERROR_MESSAGE_MAPPING = {
    RoxywiResourceNotFound: "Resource not found",
    RoxywiGroupNotFound: "Group not found",
    RoxywiGroupMismatch: "Resource not found in group",
    RoxywiPermissionError: "You do not have permission to access this resource",
    RoxywiConflictError: "Conflict with existing resource",
    RoxywiValidationError: "Validation error",
    RoxywiCheckLimits: "You have reached your plan limits",
    KeyError: "Missing required field",
    ValueError: "Invalid value provided"
}


def handle_exception(exception: Exception, additional_info: str = "", keep_history: bool = False) -> Tuple[Dict[str, Any], int]:
    """
    Handle an exception and return an appropriate HTTP response.

    Args:
        exception: The exception that was raised
        additional_info: Additional information to include in the response
        keep_history: Whether to keep the error in the action history

    Returns:
        A tuple containing the error response and HTTP status code
    """
    # Log the error
    extra = {}

    if has_request_context():
        extra['request'] = {
            'method': request.method,
            'path': request.path,
            'ip': request.remote_addr,
        }

        # Add user info if available
        if hasattr(g, 'user_params'):
            extra['user'] = {
                'id': g.user_params.get('user_id'),
                'username': g.user_params.get('user'),
                'group_id': g.user_params.get('group_id'),
            }

    log_level['error'](str(exception), extra=extra)

    # Determine the exception type and get the appropriate status code and message
    for exception_type, status_code in ERROR_CODE_MAPPING.items():
        if isinstance(exception, exception_type):
            message = ERROR_MESSAGE_MAPPING.get(exception_type, str(exception))
            if additional_info:
                message = f"{additional_info}: {message}"

            # Create the error response
            error_response = ErrorResponse(error=message).model_dump(mode='json')
            return error_response, status_code

    # If we get here, we don't have a specific handler for this exception type
    error_response = ErrorResponse(error=str(exception)).model_dump(mode='json')
    return error_response, 500


def register_error_handlers(app):
    """
    Register error handlers for the Flask application.

    Args:
        app: The Flask application
    """
    @app.errorhandler(Exception)
    def handle_exception_error(e):
        """Handle all unhandled exceptions."""
        if isinstance(e, HTTPException):
            # Pass through HTTP exceptions
            return e

        # Return a JSON response
        error_response, status_code = handle_exception(e)
        return jsonify(error_response), status_code

    # Register handlers for specific HTTP errors
    @app.errorhandler(ValidationError)
    def handle_pydantic_validation_errors(e):
        """Handle validation errors from pydantic."""
        errors = []
        if e.body_params:
            req_type = e.body_params
        elif e.form_params:
            req_type = e.form_params
        elif e.path_params:
            req_type = e.path_params
        else:
            req_type = e.query_params
        for er in req_type:
            if len(er["loc"]) > 0:
                errors.append(f'{er["loc"][0]}: {er["msg"]}')
            else:
                errors.append(er["msg"])
        return ErrorResponse(error=errors).model_dump(mode='json'), 400

    @app.errorhandler(400)
    def bad_request(e):
        """Handle 400 Bad Request errors."""
        return jsonify(ErrorResponse(error="Bad request").model_dump(mode='json')), 400

    @app.errorhandler(401)
    def unauthorized(e):
        """Handle 401 Unauthorized errors."""
        if 'api' in request.url:
            return jsonify(ErrorResponse(error=str(e)).model_dump(mode='json')), 401
        return redirect(url_for('login_page', next=request.full_path))

    @app.errorhandler(403)
    def forbidden(e):
        """Handle 403 Forbidden errors."""
        if 'api' in request.url:
            return jsonify(ErrorResponse(error=str(e)).model_dump(mode='json')), 403

        # Get user parameters for rendering the template
        get_user_params()
        kwargs = {
            'user_params': g.user_params,
            'title': e,
            'e': e
        }
        return render_template('error.html', **kwargs), 403

    @app.errorhandler(404)
    def not_found(e):
        """Handle 404 Not Found errors."""
        if 'api' in request.url:
            return jsonify(ErrorResponse(error=str(e)).model_dump(mode='json')), 404

        # Get user parameters for rendering the template
        get_user_params()
        kwargs = {
            'user_params': g.user_params,
            'title': e,
            'e': e
        }
        return render_template('error.html', **kwargs), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        """Handle 405 Method Not Allowed errors."""
        return jsonify(ErrorResponse(error=str(e)).model_dump(mode='json')), 405

    @app.errorhandler(415)
    def unsupported_media_type(e):
        """Handle 415 Unsupported Media Type errors."""
        return jsonify(ErrorResponse(error="Unsupported Media Type").model_dump(mode='json')), 415

    @app.errorhandler(429)
    def too_many_requests(e):
        """Handle 429 Too Many Requests errors."""
        return jsonify(ErrorResponse(error="Too many requests").model_dump(mode='json')), 429

    @app.errorhandler(500)
    def internal_server_error(e):
        """Handle 500 Internal Server Error errors."""
        if 'api' in request.url:
            return jsonify(ErrorResponse(error=str(e)).model_dump(mode='json')), 500

        # Get user parameters for rendering the template
        get_user_params()
        kwargs = {
            'user_params': g.user_params,
            'title': e,
            'e': e
        }
        return render_template('error.html', **kwargs), 500
