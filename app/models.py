"""Database models for the book tracker.

The schema is deliberately defined once, in full, at the foundation stage so
that later features do not need repeated schema changes. SQLite is the default
backend, but the column types and constraints are portable to PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import CheckConstraint, Index

from app import db


def _utcnow() -> datetime:
    """Return a naive UTC timestamp (portable across SQLite and PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_isbn(value: str | None) -> str | None:
    """Strip formatting from an ISBN so duplicates can be detected reliably."""
    if not value:
        return None
    normalized = "".join(char for char in value if char.isalnum()).upper()
    return normalized or None


class BookStatus:
    CURRENTLY_READING = "currently_reading"
    WANT_TO_READ = "want_to_read"
    TO_BUY = "to_buy"
    FINISHED = "finished"

    CHOICES = (
        (CURRENTLY_READING, "Currently reading"),
        (WANT_TO_READ, "Want to read"),
        (TO_BUY, "To buy"),
        (FINISHED, "Finished"),
    )
    LABELS = dict(CHOICES)


class PurchaseStatus:
    OWNED = "owned"
    TO_BUY = "to_buy"
    ORDERED = "ordered"
    UNKNOWN = "unknown"

    CHOICES = (
        (OWNED, "Owned"),
        (TO_BUY, "To buy"),
        (ORDERED, "Ordered"),
        (UNKNOWN, "Unknown"),
    )
    LABELS = dict(CHOICES)


class Book(db.Model):
    """A single book in the personal library."""

    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("current_page >= 0", name="ck_books_current_page_nonnegative"),
        CheckConstraint(
            "page_count IS NULL OR page_count >= 0", name="ck_books_page_count_nonnegative"
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)", name="ck_books_rating_range"
        ),
        Index("ix_books_title", "title"),
        Index("ix_books_status", "status"),
        Index("ix_books_isbn_normalized", "isbn_normalized", unique=True),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    authors = db.Column(db.String(300), nullable=False, default="Unknown author")
    cover_url = db.Column(db.String(1000))
    cover_small_url = db.Column(db.String(1000))
    isbn = db.Column(db.String(32))
    isbn_normalized = db.Column(db.String(32))
    publisher = db.Column(db.String(200))
    publication_year = db.Column(db.Integer)
    page_count = db.Column(db.Integer)
    current_page = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default=BookStatus.WANT_TO_READ)
    genre = db.Column(db.String(120))
    rating = db.Column(db.Integer)
    notes = db.Column(db.Text)
    review = db.Column(db.Text)
    description = db.Column(db.Text)

    purchase_status = db.Column(db.String(32), nullable=False, default=PurchaseStatus.OWNED)
    price = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(3), nullable=False, default="USD")
    purchase_link = db.Column(db.String(1000))

    date_added = db.Column(db.DateTime, nullable=False, default=_utcnow)
    date_started = db.Column(db.Date)
    date_finished = db.Column(db.Date)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    # Metadata provenance, useful for duplicate detection and cache debugging.
    source = db.Column(db.String(32), default="manual")
    external_id = db.Column(db.String(200))

    sessions = db.relationship(
        "ReadingSession",
        back_populates="book",
        cascade="all, delete-orphan",
        order_by="ReadingSession.recorded_at",
    )

    @property
    def display_authors(self) -> str:
        return self.authors or "Unknown author"

    @property
    def progress_percent(self) -> float | None:
        """Reading percentage, or None when the page count is unknown."""
        if not self.page_count or self.page_count <= 0:
            return None
        return round(min(100.0, max(0.0, self.current_page / self.page_count * 100)), 1)

    @property
    def progress_width(self) -> float:
        """Percentage used by CSS progress bars, including the finished case."""
        if self.status == BookStatus.FINISHED:
            return 100.0
        return self.progress_percent or 0.0

    @property
    def status_label(self) -> str:
        return BookStatus.LABELS.get(self.status, self.status or "Unknown")

    @property
    def purchase_status_label(self) -> str:
        return PurchaseStatus.LABELS.get(self.purchase_status, self.purchase_status or "Unknown")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Book {self.id} {self.title!r}>"


class ReadingSession(db.Model):
    """A dated snapshot of the page reached in a book.

    Storing absolute pages (not deltas) keeps the record unambiguous. Pages
    read in a period are calculated as the positive difference between
    consecutive snapshots, so repeated updates to the same page cannot inflate
    the statistics.
    """

    __tablename__ = "reading_sessions"
    __table_args__ = (
        CheckConstraint("page >= 0", name="ck_sessions_page_nonnegative"),
        Index("ix_sessions_book_recorded", "book_id", "recorded_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(
        db.Integer,
        db.ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
    )
    page = db.Column(db.Integer, nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)
    note = db.Column(db.String(255))

    book = db.relationship("Book", back_populates="sessions")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<ReadingSession book={self.book_id} page={self.page}>"


class Setting(db.Model):
    """Small key/value store for preferences such as the yearly goal."""

    __tablename__ = "settings"

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

    @classmethod
    def get_value(cls, key: str, default: str | None = None) -> str | None:
        row = db.session.get(cls, key)
        return row.value if row else default

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        try:
            return int(cls.get_value(key, str(default)) or default)
        except (TypeError, ValueError):
            return default

    @classmethod
    def set_value(cls, key: str, value: object) -> None:
        row = db.session.get(cls, key)
        if row is None:
            row = cls(key=key, value=str(value))
            db.session.add(row)
        else:
            row.value = str(value)


class SearchCache(db.Model):
    """Short-lived storage for external book-search responses."""

    __tablename__ = "search_cache"

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(255), nullable=False, unique=True, index=True)
    source = db.Column(db.String(32), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    @classmethod
    def get(cls, cache_key: str) -> list | dict | None:
        row = cls.query.filter_by(cache_key=cache_key).first()
        if row is None:
            return None
        if row.expires_at <= _utcnow():
            db.session.delete(row)
            db.session.commit()
            return None
        return row.payload

    @classmethod
    def set(cls, cache_key: str, source: str, payload: list | dict, ttl_seconds: int) -> None:
        expires_at = _utcnow() + timedelta(seconds=ttl_seconds)
        row = cls.query.filter_by(cache_key=cache_key).first()
        if row is None:
            row = cls(cache_key=cache_key, source=source)
            db.session.add(row)
        row.source = source
        row.payload = payload
        row.expires_at = expires_at
        db.session.commit()
