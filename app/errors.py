from flask import jsonify
from flask_jwt_extended.exceptions import JWTExtendedException
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from .extensions import db


def error_response(code: str, message: str, status: int):
    return jsonify({"error": {"code": code, "message": message}}), status


def register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return error_response(error.name.lower().replace(" ", "_"), error.description, error.code)

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error):
        db.session.rollback()
        app.logger.warning("Database constraint violation: %s", error)
        return error_response("conflict", "The request conflicts with existing data.", 409)

    @app.errorhandler(JWTExtendedException)
    def handle_jwt_error(error):
        return error_response("authentication_required", str(error), 401)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled exception", exc_info=error)
        return error_response("internal_error", "An unexpected error occurred.", 500)
