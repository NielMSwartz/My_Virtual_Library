"""Tests for installable-app support and production deployment config."""

from __future__ import annotations

import json

import pytest

import config as config_module
from app import create_app
from config import ProductionConfig


def test_manifest_is_served_with_correct_mime_type(client):
    response = client.get("/manifest.webmanifest")

    assert response.status_code == 200
    assert "manifest" in response.content_type

    data = json.loads(response.data)
    assert data["short_name"] == "Bookshelf"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    assert any(icon.get("purpose") == "maskable" for icon in data["icons"])


def test_service_worker_is_served_from_root_scope(client):
    response = client.get("/sw.js")

    assert response.status_code == 200
    assert "javascript" in response.content_type
    assert response.headers["Service-Worker-Allowed"] == "/"
    assert "no-store" in response.headers["Cache-Control"]


def test_offline_fallback_page(client):
    response = client.get("/offline")

    assert response.status_code == 200
    assert b"You're offline" in response.data


def test_base_template_registers_pwa_assets(client):
    response = client.get("/")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert 'rel="manifest"' in html
    assert 'name="theme-color"' in html
    assert "/sw.js" in html
    assert "apple-touch-icon" in html


def test_database_url_normalisation():
    assert config_module.normalize_database_url(None).startswith("sqlite:///")
    assert (
        config_module.normalize_database_url("postgres://user:pw@host/db")
        == "postgresql://user:pw@host/db"
    )
    assert (
        config_module.normalize_database_url("postgresql://user:pw@host/db")
        == "postgresql://user:pw@host/db"
    )
    assert (
        config_module.normalize_database_url("sqlite:////tmp/books.db")
        == "sqlite:////tmp/books.db"
    )


def test_production_requires_real_secret_key(monkeypatch):
    monkeypatch.setattr(
        ProductionConfig, "SECRET_KEY", config_module.DEVELOPMENT_SECRET_KEY
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("config.ProductionConfig")

    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a-real-secret-key")
    application = create_app("config.ProductionConfig")

    assert application.config["SESSION_COOKIE_SECURE"] is True
    assert application.config["PREFERRED_URL_SCHEME"] == "https"
