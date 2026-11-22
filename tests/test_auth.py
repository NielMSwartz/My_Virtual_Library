"""Tests for the single private account."""

from __future__ import annotations

from app.models import User
from tests.conftest import TEST_EMAIL, TEST_PASSWORD


def test_protected_page_redirects_anonymous_visitor(anonymous_client):
    response = anonymous_client.get("/")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
    assert "next=/" in response.headers["Location"]


def test_pwa_routes_stay_public(anonymous_client):
    for path in ("/manifest.webmanifest", "/sw.js", "/offline"):
        assert anonymous_client.get(path).status_code == 200


def test_signup_creates_account_and_signs_in(fresh_client, fresh_app):
    response = fresh_client.post(
        "/auth/signup",
        data={
            "email": "  ME@Example.COM  ",
            "password": "mysecret123",
            "confirm_password": "mysecret123",
        },
    )

    assert response.status_code == 302
    assert fresh_client.get("/").status_code == 200
    with fresh_app.app_context():
        user = User.query.one()
        assert user.email == "me@example.com"
        assert user.check_password("mysecret123")
        assert user.password_hash != "mysecret123"


def test_signup_is_disabled_once_account_exists(client):
    response = client.get("/auth/signup")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_login_rejects_wrong_password(client):
    client.post("/auth/logout")

    response = client.post(
        "/auth/login",
        data={"email": TEST_EMAIL, "password": "not-the-password"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "not correct" in response.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_login_accepts_correct_password_and_logout(client):
    client.post("/auth/logout")
    assert client.get("/").status_code == 302

    response = client.post(
        "/auth/login",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Welcome back" in response.get_data(as_text=True)
    assert client.get("/").status_code == 200


def test_external_next_url_is_ignored(fresh_client):
    response = fresh_client.post(
        "/auth/signup?next=https://evil.example/steal",
        data={
            "email": "reader@example.com",
            "password": "mysecret123",
            "confirm_password": "mysecret123",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_change_password_requires_current_password(client, app):
    response = client.post(
        "/auth/password",
        data={
            "current_password": "wrong-password",
            "new_password": "brandnew123",
            "confirm_password": "brandnew123",
        },
    )
    assert response.status_code == 200
    assert "current password is not correct" in response.get_data(as_text=True)

    response = client.post(
        "/auth/password",
        data={
            "current_password": TEST_PASSWORD,
            "new_password": "brandnew123",
            "confirm_password": "brandnew123",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        assert User.query.one().check_password("brandnew123")


def test_cli_can_reset_password(app):
    runner = app.test_cli_runner()

    result = runner.invoke(
        args=["reset-password", "--email", TEST_EMAIL, "--password", "resetme123"]
    )

    assert result.exit_code == 0, result.output
    with app.app_context():
        assert User.query.one().check_password("resetme123")
