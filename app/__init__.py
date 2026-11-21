"""Flask application factory for the personal book tracker."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path

from flask import Flask, render_template
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import DEVELOPMENT_SECRET_KEY

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()

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

    # Flask-SQLAlchemy resolves relative SQLite paths against the instance
    # folder, which is also where the local database and migrations live.
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Import models so Flask-Migrate can discover every table.
    from app import models  # noqa: F401

    from app.routes import register_blueprints

    register_blueprints(app)

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
