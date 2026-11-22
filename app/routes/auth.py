"""Sign-up, sign-in and account routes for the single private bookshelf."""

from __future__ import annotations

from urllib.parse import urlparse

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.forms import ChangePasswordForm, LoginForm, LogoutForm, SetupForm
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next(target: str | None) -> str:
    """Only allow same-site relative paths after sign-in."""
    if not target:
        return url_for("dashboard.index")
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc or not target.startswith("/") or target.startswith("//"):
        return url_for("dashboard.index")
    return target


@auth_bp.route("/signup", methods=["GET", "POST"])
def setup():
    """Create the one account. Disabled once it exists."""
    if User.count() > 0:
        return redirect(url_for("auth.login"))

    form = SetupForm()
    if form.validate_on_submit():
        user = User(email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Your bookshelf is ready. Welcome!", "success")
        return redirect(_safe_next(request.args.get("next")))

    return render_template("auth/setup.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Sign in with the account email address and password."""
    if User.count() == 0:
        return redirect(url_for("auth.setup", next=request.args.get("next")))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.find_by_email(form.email.data)
        # The same message is used for an unknown email and a wrong password.
        if user is None or not user.check_password(form.password.data):
            flash("That email and password combination is not correct.", "error")
        else:
            login_user(user, remember=form.remember.data)
            flash("Welcome back.", "success")
            return redirect(_safe_next(request.args.get("next")))

    return render_template("auth/login.html", form=form)


@auth_bp.post("/logout")
def logout():
    """End the session. A POST keeps logout CSRF-protected."""
    form = LogoutForm()
    if not form.validate_on_submit():
        abort(400)
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    """Let the account owner replace their password."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            form.current_password.errors.append("Your current password is not correct.")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Password changed.", "success")
            return redirect(url_for("settings.index"))

    return render_template("auth/change_password.html", form=form)
