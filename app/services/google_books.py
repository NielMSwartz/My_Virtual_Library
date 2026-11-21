"""Google Books volume search (works without an API key for normal use)."""

from __future__ import annotations

import logging
import re

import requests
from flask import current_app

from app.services import MetadataError

API_URL = "https://www.googleapis.com/books/v1/volumes"
logger = logging.getLogger(__name__)


def _upgrade_cover(url: str | None, zoom: int) -> str | None:
    """Use HTTPS and request a larger Google Books thumbnail when possible."""
    if not url:
        return None
    upgraded = url.replace("http://", "https://", 1)
    if "zoom=" in upgraded:
        upgraded = re.sub(r"zoom=\d+", f"zoom={zoom}", upgraded)
    else:
        upgraded += ("&" if "?" in upgraded else "?") + f"zoom={zoom}"
    return upgraded


def _clean_description(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:700]


def _parse_item(item: dict) -> dict:
    info = item.get("volumeInfo") or {}
    identifiers = info.get("industryIdentifiers") or []
    isbn = ""
    for identifier_type in ("ISBN_13", "ISBN_10"):
        for identifier in identifiers:
            if identifier.get("type") == identifier_type:
                isbn = identifier.get("identifier", "")
                break
        if isbn:
            break

    links = info.get("imageLinks") or {}
    small = links.get("smallThumbnail") or links.get("thumbnail")
    large = links.get("thumbnail") or links.get("smallThumbnail")

    published = str(info.get("publishedDate") or "")
    year = int(published[:4]) if published[:4].isdigit() else None
    categories = info.get("categories") or []

    return {
        "source": "google_books",
        "external_id": item.get("id", ""),
        "title": info.get("title") or "",
        "subtitle": info.get("subtitle") or "",
        "authors": ", ".join(info.get("authors") or []),
        "cover_url": _upgrade_cover(large, 2),
        "cover_small_url": _upgrade_cover(small, 1),
        "isbn": isbn,
        "publisher": info.get("publisher") or "",
        "publication_year": year,
        "page_count": info.get("pageCount") if isinstance(info.get("pageCount"), int) else None,
        "description": _clean_description(info.get("description")),
        "genre": categories[0] if categories else "",
    }


def search(query: str) -> list[dict]:
    """Return normalised search results, or raise MetadataError on failure."""
    params = {"q": query, "maxResults": 12, "printType": "books"}
    api_key = current_app.config.get("GOOGLE_BOOKS_API_KEY")
    if api_key:
        params["key"] = api_key

    try:
        response = requests.get(
            API_URL, params=params, timeout=current_app.config.get("REQUEST_TIMEOUT", 8)
        )
    except requests.RequestException as exc:
        logger.warning("Google Books request failed: %s", exc)
        raise MetadataError("Google Books could not be reached right now.") from exc

    if response.status_code == 429:
        raise MetadataError("Google Books is rate-limiting requests right now.")
    if response.status_code >= 500:
        raise MetadataError("Google Books is temporarily unavailable.")
    if not response.ok:
        logger.warning("Google Books returned HTTP %s", response.status_code)
        raise MetadataError("Google Books could not complete the search.")

    try:
        payload = response.json()
    except ValueError as exc:
        raise MetadataError("Google Books returned an unreadable response.") from exc

    items = payload.get("items") or []
    return [_parse_item(item) for item in items if item.get("volumeInfo", {}).get("title")]
