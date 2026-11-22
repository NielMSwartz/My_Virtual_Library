"""Application configuration.

Values are read from environment variables so the same code can run locally,
in tests, and later against PostgreSQL. See .env.example for documentation.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from sqlalchemy.pool import StaticPool

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "instance" / "book_tracker.db"
DEVELOPMENT_SECRET_KEY = "development-only-change-me"


def normalize_database_url(url: str | None) -> str:
    """Return a SQLAlchemy 2.x compatible database URL.

    Render and Heroku still hand out ``postgres://`` URLs, while SQLAlchemy 2
    requires the ``postgresql://`` scheme. Everything else is left untouched.
    """
    if not url:
        return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


class Config:
    """Shared defaults for every environment."""

    SECRET_KEY = os.environ.get("SECRET_KEY", DEVELOPMENT_SECRET_KEY)
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    WTF_CSRF_ENABLED = True

    # External book metadata services.
    GOOGLE_BOOKS_API_KEY = os.environ.get("GOOGLE_BOOKS_API_KEY") or None
    OPEN_LIBRARY_ENABLED = os.environ.get("OPEN_LIBRARY_ENABLED", "1") != "0"
    REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "8"))
    SEARCH_CACHE_TTL_SECONDS = int(
        os.environ.get("SEARCH_CACHE_TTL_SECONDS", str(7 * 24 * 60 * 60))
    )


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-only-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    PREFERRED_URL_SCHEME = "https"
