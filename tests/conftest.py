"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app import create_app, db as database
from app.models import User
from config import TestingConfig

TEST_EMAIL = "reader@example.com"
TEST_PASSWORD = "booklover123"


@pytest.fixture()
def app():
    application = create_app(TestingConfig)
    with application.app_context():
        database.create_all()
        user = User(email=TEST_EMAIL)
        user.set_password(TEST_PASSWORD)
        database.session.add(user)
        database.session.commit()
        yield application
        database.session.remove()
        database.drop_all()


@pytest.fixture()
def client(app):
    test_client = app.test_client()
    response = test_client.post(
        "/auth/login",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code == 302, "The shared client fixture must sign in successfully."
    return test_client


@pytest.fixture()
def anonymous_client(app):
    return app.test_client()


@pytest.fixture()
def fresh_app():
    """An app with no account, for testing first-run sign-up."""
    application = create_app(TestingConfig)
    with application.app_context():
        database.create_all()
        yield application
        database.session.remove()
        database.drop_all()


@pytest.fixture()
def fresh_client(fresh_app):
    return fresh_app.test_client()
