"""Helpers for keeping the local catalogue clean and duplicate-free."""

from __future__ import annotations

import re
import unicodedata

from app.models import Book, normalize_isbn


def normalize_text(value: str | None) -> str:
    """Lowercase, de-accent and strip punctuation from comparison text."""
    if not value:
        return ""
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def first_author(authors: str | None) -> str:
    """Primary author, as names are stored comma- or semicolon-separated."""
    if not authors:
        return ""
    return re.split(r"[,;]", authors, maxsplit=1)[0].strip()


def find_duplicate(
    title: str | None,
    authors: str | None,
    isbn: str | None = None,
    exclude_id: int | None = None,
) -> Book | None:
    """Return an existing book matching the ISBN or title + primary author.

    ISBN is the strongest signal. When it is absent (common with online
    results), a normalised title/author comparison catches most duplicates.
    """
    query = Book.query
    if exclude_id is not None:
        query = query.filter(Book.id != exclude_id)

    isbn_key = normalize_isbn(isbn)
    if isbn_key:
        match = query.filter(Book.isbn_normalized == isbn_key).first()
        if match is not None:
            return match

    title_key = normalize_text(title)
    author_key = normalize_text(first_author(authors))
    if not title_key or not author_key:
        return None

    # Personal libraries are small; comparing normalised strings is cheap and
    # avoids fragile database-specific collation rules.
    for candidate in query.all():
        if (
            normalize_text(candidate.title) == title_key
            and normalize_text(first_author(candidate.authors)) == author_key
        ):
            return candidate
    return None
