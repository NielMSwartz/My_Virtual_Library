"""Copy the local SQLite library into a migrated target database.

Use this once after deploying the account update. It copies books, dated reading
sessions and the yearly goal, and creates the first sign-in if the target has no
account yet. Search-cache rows are deliberately not copied.

PowerShell example (use Render's *External Database URL* locally):

    $env:DATABASE_URL = "postgresql://..."
    python scripts/transfer_library.py --email you@example.com

The target must already have the latest schema:

    $env:FLASK_APP = "run.py"
    flask db upgrade
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import sqlite3
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.types import Boolean, Date, DateTime, Numeric
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import Config, DEFAULT_DB_PATH, normalize_database_url  # noqa: E402
from app import create_app, db  # noqa: E402

TABLES = ("settings", "books", "reading_sessions")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TransferConfig(Config):
    """A throwaway app config pointed at the target database.

    ``SQLALCHEMY_DATABASE_URI`` is assigned in ``main()`` from --target, so it
    deliberately is not inherited from Config here.
    """

    TESTING = True
    SECRET_KEY = secrets.token_hex(32)
    WTF_CSRF_ENABLED = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Local SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("DATABASE_URL"),
        help="Target SQLAlchemy URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--email",
        help="Email for the first account. Prompted for if the target has no account.",
    )
    parser.add_argument(
        "--password",
        help="New password. Omit to be prompted securely (avoids shell history).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace books already in the target database.",
    )
    return parser.parse_args()


def _convert(value, column_type):
    if value is None:
        return None
    # DateTime must be checked first because it subclasses Date in SQLAlchemy.
    if isinstance(column_type, DateTime) and isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(column_type, Date) and isinstance(value, str):
        return date.fromisoformat(value[:10])
    if isinstance(column_type, Numeric):
        return Decimal(str(value))
    if isinstance(column_type, Boolean) and isinstance(value, int):
        return bool(value)
    return value


def _read_source(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        raise SystemExit(f"Local database not found: {path}")

    source = sqlite3.connect(path)
    try:
        source.row_factory = sqlite3.Row
        present = {
            row[0]
            for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        missing = set(TABLES) - present
        if missing:
            raise SystemExit(
                "Local database is missing: " + ", ".join(sorted(missing)) +
                ". Run 'flask db upgrade' locally first."
            )
        return {
            table: [dict(row) for row in source.execute(f"SELECT * FROM {table}")]
            for table in TABLES
        }
    finally:
        source.close()


def _target_columns() -> dict[str, dict[str, object]]:
    inspector = inspect(db.engine)
    present = set(inspector.get_table_names())
    required = set(TABLES) | {"users"}
    missing = required - present
    if missing:
        raise SystemExit(
            "Target database is missing: " + ", ".join(sorted(missing)) +
            ". Set DATABASE_URL to the target, then run 'flask db upgrade' there first."
        )
    return {
        table: {column["name"]: column["type"] for column in inspector.get_columns(table)}
        for table in TABLES
    }


def _count(table: str) -> int:
    return int(db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())


def _clear_library() -> None:
    for table in ("reading_sessions", "books", "settings"):
        db.session.execute(text(f"DELETE FROM {table}"))


def _insert_rows(table: str, rows: list[dict], columns: dict[str, object]) -> int:
    if not rows:
        return 0
    names = [name for name in rows[0] if name in columns]
    if not names:
        return 0
    statement = text(
        f"INSERT INTO {table} ({', '.join(names)}) "
        f"VALUES ({', '.join(':' + name for name in names)})"
    )
    for row in rows:
        db.session.execute(
            statement,
            {name: _convert(row.get(name), columns[name]) for name in names},
        )
    return len(rows)


def _reset_postgres_sequences() -> None:
    if db.engine.dialect.name != "postgresql":
        return
    for table in ("books", "reading_sessions"):
        db.session.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1), "
                f"EXISTS (SELECT 1 FROM {table}))"
            )
        )


def _ensure_account(email_arg: str | None, password_arg: str | None) -> str | None:
    if _count("users"):
        return None

    email = (email_arg or input("Email for the new account: ")).strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise SystemExit("Enter a valid email address.")

    if password_arg:
        password = password_arg
    else:
        password = getpass.getpass("Password (at least 8 characters): ")
        if password != getpass.getpass("Confirm password: "):
            raise SystemExit("Passwords do not match.")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters long.")

    db.session.execute(
        text("INSERT INTO users (email, password_hash, created_at) VALUES (:email, :hash, :created)"),
        {
            "email": email,
            "hash": generate_password_hash(password),
            "created": datetime.now(),
        },
    )
    return email


def main() -> None:
    args = parse_args()
    if not args.target:
        raise SystemExit(
            "No target database. Pass --target or set DATABASE_URL to the target URL."
        )

    source_rows = _read_source(args.source)
    target_url = normalize_database_url(args.target)
    TransferConfig.SQLALCHEMY_DATABASE_URI = target_url
    application = create_app(TransferConfig)

    with application.app_context():
        columns = _target_columns()
        existing = _count("books")
        if existing and not args.force:
            raise SystemExit(
                f"The target already has {existing} books. Re-run with --force to replace them."
            )
        if existing:
            answer = input(
                f"This deletes {existing} target books and their sessions. Type DELETE to continue: "
            )
            if answer != "DELETE":
                raise SystemExit("Transfer cancelled.")
            _clear_library()

        counts = {
            table: _insert_rows(table, source_rows[table], columns[table])
            for table in TABLES
        }
        _reset_postgres_sequences()
        created_email = _ensure_account(args.email, args.password)
        db.session.commit()

    print(f"Copied to {target_url.split('@')[-1]}:")
    print(f"  settings:         {counts['settings']}")
    print(f"  books:            {counts['books']}")
    print(f"  reading sessions: {counts['reading_sessions']}")
    if created_email:
        print(f"  account created:  {created_email}")
    else:
        print("  account:          existing sign-in left unchanged")


if __name__ == "__main__":
    main()
