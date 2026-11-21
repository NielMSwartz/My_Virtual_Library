"""Tests for the light/dark theme support."""

from __future__ import annotations


def test_theme_script_is_served(client):
    response = client.get("/static/js/theme.js")

    assert response.status_code == 200
    assert b"bookshelf-theme" in response.data


def test_base_template_includes_theme_controls(client):
    response = client.get("/")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "data-theme" in html
    assert "data-theme-toggle" in html
    assert "prefers-color-scheme" in html
    assert "/static/js/theme.js" in html


def test_stylesheet_defines_dark_theme(client):
    response = client.get("/static/css/style.css")

    assert response.status_code == 200
    assert b'html[data-theme="dark"]' in response.data
