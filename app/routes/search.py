"""External book discovery endpoint (local library search lives in books.py)."""

from __future__ import annotations

import copy

from flask import Blueprint, jsonify, request

from app.services.book_catalog import find_duplicate
from app.services.metadata import search_books

search_bp = Blueprint("search", __name__, url_prefix="/search")


@search_bp.route("/online")
def online():
    query = request.args.get("q", "").strip()
    provider = request.args.get("source", "auto").strip()
    if provider not in ("auto", "google", "open_library"):
        provider = "auto"

    if len(query) < 2:
        return jsonify(
            query=query, source=None, results=[], warning="Enter at least two characters to search."
        )

    payload = copy.deepcopy(search_books(query, provider))

    # Annotate at request time so the cached payload never goes stale when the
    # user adds a book that was previously listed as a search result.
    for result in payload["results"]:
        duplicate = find_duplicate(
            result.get("title"), result.get("authors"), result.get("isbn")
        )
        result["in_library"] = duplicate is not None
        result["book_id"] = duplicate.id if duplicate else None

    return jsonify(payload)
