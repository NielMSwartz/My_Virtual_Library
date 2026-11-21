"""Dashboard route."""

from __future__ import annotations

from flask import Blueprint, render_template

from app.services.reading_stats import build_statistics

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    stats = build_statistics()
    return render_template(
        "dashboard.html",
        stats=stats,
        counts=stats["counts"],
        total_books=stats["total_books"],
        recently_updated=stats["recently_updated"],
    )
