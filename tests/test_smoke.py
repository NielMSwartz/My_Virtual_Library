"""Foundation smoke tests: the app boots, routes resolve and data persists."""

import pytest

from app import db
from app.models import Book, BookStatus


def test_dashboard_renders_with_zero_counts(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Books in library" in html
    assert "Your shelf is waiting" in html


def test_navigation_links_resolve(client):
    html = client.get("/").get_data(as_text=True)
    for fragment in ("/books/", "/books/new", "/statistics/", "/settings/"):
        assert fragment in html


@pytest.mark.parametrize("path", ["/", "/books/", "/books/new", "/statistics/", "/settings/"])
def test_main_pages_render(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert "Bookshelf" in response.get_data(as_text=True)


def test_unknown_route_uses_friendly_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert "That page isn't on the shelf" in response.get_data(as_text=True)


def test_book_record_persists_in_database(app):
    book = Book(
        title="The Hobbit",
        authors="J.R.R. Tolkien",
        status=BookStatus.CURRENTLY_READING,
        page_count=310,
        current_page=142,
    )
    db.session.add(book)
    db.session.commit()
    book_id = book.id

    # A fresh session reads the same row, proving data is in the database and
    # not held in application state or the browser.
    db.session.remove()
    stored = db.session.get(Book, book_id)
    assert stored.title == "The Hobbit"
    assert stored.progress_percent == 45.8
