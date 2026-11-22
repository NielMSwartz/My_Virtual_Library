"""Settings route for the yearly reading goal."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for

from app import db
from app.forms import LogoutForm, SettingsForm
from app.models import Setting
from app.services.reading_stats import build_statistics, current_year, yearly_goal

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/", methods=["GET", "POST"])
def index():
    form = SettingsForm(yearly_goal=yearly_goal())
    if form.validate_on_submit():
        Setting.set_value("reading_goal", form.yearly_goal.data or 0)
        db.session.commit()
        flash("Reading goal saved.", "success")
        return redirect(url_for("settings.index"))

    return render_template(
        "settings.html",
        form=form,
        stats=build_statistics(),
        year=current_year(),
        logout_form=LogoutForm(),
    )
