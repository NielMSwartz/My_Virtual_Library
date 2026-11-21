"""Reading statistics route."""

from __future__ import annotations

from flask import Blueprint, render_template

from app.services.reading_stats import build_statistics, current_year

statistics_bp = Blueprint("statistics", __name__, url_prefix="/statistics")

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@statistics_bp.route("/")
def index():
    stats = build_statistics()
    return render_template(
        "statistics.html",
        stats=stats,
        year=current_year(),
        months=MONTHS,
        monthly_max=max(stats["completed_by_month"].values(), default=0) or 1,
        genre_max=max(stats["genres"].values(), default=1),
    )
