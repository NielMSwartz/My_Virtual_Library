"""Routes that make the app installable as a Progressive Web App."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, send_from_directory

pwa_bp = Blueprint("pwa", __name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@pwa_bp.get("/manifest.webmanifest")
def manifest() -> Response:
    """Serve the web app manifest with the correct MIME type."""
    return send_from_directory(
        STATIC_DIR,
        "manifest.webmanifest",
        mimetype="application/manifest+json",
    )


@pwa_bp.get("/sw.js")
def service_worker() -> Response:
    """Serve the service worker from the root scope, never from cache."""
    response = send_from_directory(
        STATIC_DIR, "sw.js", mimetype="application/javascript"
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@pwa_bp.get("/offline")
def offline() -> Response:
    """Fallback page shown by the service worker when there is no connection."""
    return send_from_directory(STATIC_DIR, "offline.html", mimetype="text/html")
