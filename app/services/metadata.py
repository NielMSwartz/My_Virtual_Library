"""Cached, failure-tolerant orchestration of the external book providers."""

from __future__ import annotations

from flask import current_app

from app.models import SearchCache
from app.services import MetadataError, google_books, open_library


def search_books(query: str, provider: str = "auto") -> dict:
    """Search external catalogues and return a cacheable payload.

    ``provider`` is one of ``auto``, ``google`` or ``open_library``. In auto
    mode Google Books is tried first and Open Library is used when Google has
    no results or is unavailable.
    """
    query = query.strip()
    cache_key = f"search:{provider}:{query.casefold()}"
    cached = SearchCache.get(cache_key)
    if cached is not None:
        return cached

    results: list[dict] = []
    warnings: list[str] = []
    source = "google_books"

    if provider in ("auto", "google"):
        try:
            results = google_books.search(query)
        except MetadataError as exc:
            warnings.append(str(exc))
    elif provider == "open_library":
        source = "open_library"

    if provider == "open_library" or (provider == "auto" and not results):
        if current_app.config.get("OPEN_LIBRARY_ENABLED", True):
            source = "open_library"
            try:
                results = open_library.search(query)
            except MetadataError as exc:
                warnings.append(str(exc))

    payload = {
        "query": query,
        "source": source,
        "results": results,
        "warning": " ".join(dict.fromkeys(warnings)) if warnings else None,
    }

    # Never cache failures; a later retry should be allowed to recover.
    if not warnings:
        SearchCache.set(
            cache_key,
            source,
            payload,
            current_app.config.get("SEARCH_CACHE_TTL_SECONDS", 604800),
        )
    return payload
