"""Flask application factory for the personal book tracker."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import DEVELOPMENT_SECRET_KEY

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()

# Pages that must stay reachable before sign-in (including Render health checks
# and the offline PWA shell).
PUBLIC_ENDPOINTS = {
    "static",
    "auth.login",
    "auth.setup",
    "pwa.manifest",
    "pwa.service_worker",
    "pwa.offline",
}

_CONFIG_MAP = {
    "development": "config.DevelopmentConfig",
    "testing": "config.TestingConfig",
    "production": "config.ProductionConfig",
}


def create_app(config_object: object | str | None = None) -> Flask:
    """Build and configure a Flask application instance."""
    app = Flask(__name__, instance_relative_config=True)

    if config_object is None:
        config_object = os.environ.get("FLASK_CONFIG", "config.DevelopmentConfig")
        if config_object.lower() in _CONFIG_MAP:
            config_object = _CONFIG_MAP[config_object.lower()]
    app.config.from_object(config_object)

    if (
        not app.debug
        and not app.testing
        and app.config["SECRET_KEY"] == DEVELOPMENT_SECRET_KEY
    ):
        raise RuntimeError(
            "SECRET_KEY must be set to a long random value in production. "
            "Set the SECRET_KEY environment variable before starting the app."
        )

    # In production SQLite would live on Render's temporary filesystem and be
    # wiped on every rebuild. Fail loudly instead of silently losing data.
    if (
        not app.debug
        and not app.testing
        and str(app.config["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite:///")
    ):
        raise RuntimeError(
            "DATABASE_URL must point to the Render Postgres database in "
            "production. Without it the app falls back to temporary SQLite "
            "storage and every rebuild erases your books."
        )

    # Flask-SQLAlchemy resolves relative SQLite paths against the instance
    # folder, which is also where the local database and migrations live.
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Sign in to open your bookshelf."
    login_manager.login_message_category = "error"

    # Import models so Flask-Migrate can discover every table.
    from app import models  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(models.User, int(user_id))
        except (TypeError, ValueError):
            return None

    @app.before_request
    def require_account():
        endpoint = request.endpoint
        if (
            endpoint is None
            or endpoint in PUBLIC_ENDPOINTS
            or endpoint.startswith("auth.")
            or current_user.is_authenticated
        ):
            return None
        next_url = request.full_path.rstrip("?") if request.query_string else request.path
        return redirect(url_for("auth.login", next=next_url))

    from app.routes import register_blueprints
    from app.cli import register_cli

    register_blueprints(app)
    register_cli(app)

    @app.template_filter("date_display")
    def date_display(value: date | datetime | None) -> str:
        if value is None:
            return "—"
        if isinstance(value, datetime):
            value = value.date()
        return value.strftime("%b %d, %Y")

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        # The exception has already been logged by Flask. Never show a traceback.
        db.session.rollback()
        return render_template("errors/500.html"), 500

    return app
