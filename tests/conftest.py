"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app import create_app, db as database
from config import TestingConfig


@pytest.fixture()
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        database.create_all()
        yield application
        database.session.remove()
        database.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()
