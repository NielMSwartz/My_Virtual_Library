"""Optional Open Library fallback for book metadata and covers."""

from __future__ import annotations

import logging

import requests
from flask import current_app

from app.services import MetadataError

API_URL = "https://openlibrary.org/search.json"
logger = logging.getLogger(__name__)


def _cover_urls(cover_id: int | None) -> tuple[str | None, str | None]:
    if not cover_id:
        return None, None
    return (
        f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg",
        f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
    )


def _parse_doc(doc: dict) -> dict:
    cover_large, cover_small = _cover_urls(doc.get("cover_i"))
    isbns = doc.get("isbn") or []
    year = doc.get("first_publish_year")
    subjects = doc.get("subject") or []

    return {
        "source": "open_library",
        "external_id": doc.get("key", ""),
        "title": doc.get("title") or "",
        "subtitle": "",
        "authors": ", ".join((doc.get("author_name") or [])[:3]),
        "cover_url": cover_large,
        "cover_small_url": cover_small,
        "isbn": isbns[0] if isbns else "",
        "publisher": (doc.get("publisher") or [""])[0],
        "publication_year": year if isinstance(year, int) else None,
        "page_count": doc.get("number_of_pages_median"),
        "description": "",
        "genre": subjects[0] if subjects else "",
    }


def search(query: str) -> list[dict]:
    params = {
        "q": query,
        "limit": 12,
        "fields": (
            "key,title,author_name,first_publish_year,cover_i,isbn,publisher,"
            "number_of_pages_median,subject"
        ),
    }
    try:
        response = requests.get(
            API_URL, params=params, timeout=current_app.config.get("REQUEST_TIMEOUT", 8)
        )
    except requests.RequestException as exc:
        logger.warning("Open Library request failed: %s", exc)
        raise MetadataError("Open Library could not be reached right now.") from exc

    if response.status_code == 429:
        raise MetadataError("Open Library is rate-limiting requests right now.")
    if response.status_code >= 500:
        raise MetadataError("Open Library is temporarily unavailable.")
    if not response.ok:
        raise MetadataError("Open Library could not complete the search.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise MetadataError("Open Library returned an unreadable response.") from exc

    docs = payload.get("docs") or []
    return [_parse_doc(doc) for doc in docs if doc.get("title")]
