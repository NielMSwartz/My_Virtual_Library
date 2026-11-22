"""External search parsing, caching, fallback and error handling."""

import requests

from app import db
from app.models import Book, SearchCache


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._payload


def google_item():
    return {
        "id": "volume-123",
        "volumeInfo": {
            "title": "The Hobbit",
            "subtitle": "There and Back Again",
            "authors": ["J.R.R. Tolkien"],
            "publishedDate": "2012-09-20",
            "pageCount": 310,
            "publisher": "HarperCollins",
            "categories": ["Fiction / Fantasy"],
            "industryIdentifiers": [
                {"type": "ISBN_10", "identifier": "0261103342"},
                {"type": "ISBN_13", "identifier": "9780261103344"},
            ],
            "imageLinks": {
                "thumbnail": "http://books.google.com/books/content?id=volume-123&img=1&zoom=1",
                "smallThumbnail": "http://books.google.com/books/content?id=volume-123&img=1&zoom=1",
            },
            "description": "<p>An <b>unexpected</b> journey.</p>",
        },
    }


def open_library_doc():
    return {
        "key": "/works/OL45804W",
        "title": "Dune",
        "author_name": ["Frank Herbert"],
        "first_publish_year": 1965,
        "cover_i": 12345,
        "isbn": ["9780441013593"],
        "publisher": ["Ace Books"],
        "number_of_pages_median": 412,
        "subject": ["Science fiction"],
    }


def test_google_results_are_normalised(client, monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured.update(params or {})
        return FakeResponse(payload={"items": [google_item()]})

    monkeypatch.setattr(requests, "get", fake_get)
    # An optional key may be set in the developer's environment; this test
    # checks that a plain search works without one.
    monkeypatch.setitem(client.application.config, "GOOGLE_BOOKS_API_KEY", None)

    response = client.get("/search/online?q=hobbit")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["source"] == "google_books"
    result = payload["results"][0]
    assert result["title"] == "The Hobbit"
    assert result["authors"] == "J.R.R. Tolkien"
    assert result["isbn"] == "9780261103344"
    assert result["publication_year"] == 2012
    assert result["page_count"] == 310
    assert result["genre"] == "Fiction / Fantasy"
    assert result["description"] == "An unexpected journey."
    assert result["cover_url"].startswith("https://")
    assert "zoom=2" in result["cover_url"]
    assert "key" not in captured  # basic search needs no configured key


def test_search_results_are_cached(client, monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return FakeResponse(payload={"items": [google_item()]})

    monkeypatch.setattr(requests, "get", fake_get)

    client.get("/search/online?q=hobbit")
    client.get("/search/online?q=hobbit")

    assert len(calls) == 1
    assert SearchCache.query.count() == 1


def test_open_library_fallback_when_google_has_no_results(client, monkeypatch):
    def fake_get(url, params=None, timeout=None):
        if "googleapis" in url:
            return FakeResponse(payload={"items": []})
        return FakeResponse(payload={"docs": [open_library_doc()]})

    monkeypatch.setattr(requests, "get", fake_get)

    payload = client.get("/search/online?q=dune").get_json()
    assert payload["source"] == "open_library"
    assert payload["results"][0]["title"] == "Dune"
    assert payload["results"][0]["cover_url"].endswith("-L.jpg")


def test_provider_failures_are_reported_without_crashing(client, monkeypatch):
    def fake_get(url, params=None, timeout=None):
        raise requests.Timeout("network down")

    monkeypatch.setattr(requests, "get", fake_get)

    response = client.get("/search/online?q=hobbit")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["results"] == []
    assert "could not be reached" in payload["warning"].lower()
    assert SearchCache.query.count() == 0


def test_existing_books_are_flagged_in_results(client, monkeypatch):
    db.session.add(
        Book(title="The Hobbit", authors="J.R.R. Tolkien", isbn="9780261103344", isbn_normalized="9780261103344")
    )
    db.session.commit()

    monkeypatch.setattr(
        requests, "get", lambda url, params=None, timeout=None: FakeResponse(payload={"items": [google_item()]})
    )

    result = client.get("/search/online?q=hobbit").get_json()["results"][0]
    assert result["in_library"] is True
    assert result["book_id"] is not None


def test_short_queries_do_not_call_external_apis(client, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("should not call the network")

    monkeypatch.setattr(requests, "get", fail)
    payload = client.get("/search/online?q=a").get_json()
    assert payload["results"] == []
    assert "two characters" in payload["warning"]
