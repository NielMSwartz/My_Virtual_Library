"""Blueprint registration for the application."""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.routes.auth import auth_bp
    from app.routes.books import books_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.pwa import pwa_bp
    from app.routes.search import search_bp
    from app.routes.settings import settings_bp
    from app.routes.statistics import statistics_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pwa_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(settings_bp)
