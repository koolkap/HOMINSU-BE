import click
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager

from .config import Config
from .errors import error_response, register_error_handlers
from .extensions import cors, db, jwt, migrate


def create_app(config_object=None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_object:
        app.config.from_mapping(config_object) if isinstance(config_object, dict) else app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from . import models  # noqa: F401
    from .account import bp as account_bp
    from .auth import bp as auth_bp
    from .catalog import bp as catalog_bp
    from .operator import bp as operator_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(catalog_bp, url_prefix="/api/v1")
    app.register_blueprint(account_bp, url_prefix="/api/v1")
    app.register_blueprint(operator_bp, url_prefix="/api/v1")

    @app.get("/health")
    def health():
        return jsonify({"data": {"status": "ok"}})

    @app.cli.command("seed")
    def seed_command():
        from .seed import seed_database

        seed_database()
        click.echo("Seed data is ready.")

    register_jwt_handlers(jwt)
    register_error_handlers(app)
    return app


def register_jwt_handlers(jwt_manager: JWTManager) -> None:
    @jwt_manager.unauthorized_loader
    def missing_token(message):
        return error_response("authentication_required", message, 401)

    @jwt_manager.invalid_token_loader
    def invalid_token(message):
        return error_response("invalid_token", message, 422)

    @jwt_manager.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response("token_expired", "The access token has expired.", 401)
