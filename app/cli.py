"""Small Flask CLI commands for managing the single private account."""

from __future__ import annotations

import re

import click
from flask import Flask

from app import db
from app.models import User

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate(email: str, password: str) -> tuple[str, str]:
    normalized = User.normalize_email(email)
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise click.ClickException("Enter a valid email address.")
    if len(password) < 8:
        raise click.ClickException("Password must be at least 8 characters long.")
    return normalized, password


def register_cli(app: Flask) -> None:
    """Attach account-management commands to ``flask``."""

    @app.cli.command("create-account")
    @click.option("--email", prompt="Email address", help="Sign-in email for the bookshelf.")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Password (at least 8 characters).",
    )
    def create_account(email: str, password: str) -> None:
        """Create the first (and only) account."""
        email, password = _validate(email, password)
        with app.app_context():
            if User.count():
                raise click.ClickException(
                    "An account already exists. Use 'flask reset-password' instead."
                )
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        click.echo(f"Account created for {email}.")

    @app.cli.command("reset-password")
    @click.option("--email", prompt="Email address", help="Account email to reset.")
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="New password (at least 8 characters).",
    )
    def reset_password(email: str, password: str) -> None:
        """Reset the password if it has been forgotten."""
        email, password = _validate(email, password)
        with app.app_context():
            user = User.find_by_email(email)
            if user is None:
                raise click.ClickException(f"No account found for {email}.")
            user.set_password(password)
            db.session.commit()
        click.echo(f"Password updated for {email}.")

    @app.cli.command("list-accounts")
    def list_accounts() -> None:
        """Show the email address of the existing account."""
        with app.app_context():
            users = db.session.query(User).order_by(User.id).all()
            if not users:
                click.echo("No account yet. Open the app to sign up, or run 'flask create-account'.")
                return
            for user in users:
                click.echo(f"{user.id}: {user.email}")
