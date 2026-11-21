"""Digital bookmark, progress validation and completion workflow tests."""

import re

from app import db
from app.models import Book, BookStatus, ReadingSession


def create_book(client, **overrides):
    payload = {
        "title": "The Hobbit",
        "authors": "J.R.R. Tolkien",
        "status": BookStatus.CURRENTLY_READING,
        "page_count": "310",
        "current_page": "20",
        "genre": "Fantasy",
        "rating": "0",
        "purchase_status": "owned",
        "currency": "USD",
        "source": "manual",
    }
    payload.update(overrides)
    client.post("/books/new", data=payload)
    return Book.query.one()


def csrf_from(client, path):
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert match, "CSRF meta tag missing"
    return match.group(1)


def test_progress_update_saves_page_and_creates_session(client):
    book = create_book(client)
    response = client.post(
        f"/books/{book.id}/progress", data={"page": "142"}, follow_redirects=True
    )
    assert response.status_code == 200

    db.session.refresh(book)
    assert book.current_page == 142
    assert book.progress_percent == 45.8
    assert ReadingSession.query.count() == 1
    assert ReadingSession.query.one().page == 142
    assert "page 142 of 310" in response.get_data(as_text=True)


def test_progress_update_persists_after_new_request(client):
    book = create_book(client)
    client.post(f"/books/{book.id}/progress", data={"page": "200"})

    html = client.get(f"/books/{book.id}").get_data(as_text=True)
    assert "Page 200 of 310" in html
    assert 'value="200"' in html


def test_out_of_range_page_is_rejected(client):
    book = create_book(client)
    response = client.post(
        f"/books/{book.id}/progress", data={"page": "999"}, follow_redirects=True
    )
    db.session.refresh(book)
    assert book.current_page == 20
    assert ReadingSession.query.count() == 0
    assert "cannot be greater" in response.get_data(as_text=True)


def test_negative_page_is_rejected(client):
    book = create_book(client)
    response = client.post(
        f"/books/{book.id}/progress", data={"page": "-3"}, follow_redirects=True
    )
    db.session.refresh(book)
    assert book.current_page == 20
    assert "cannot be negative" in response.get_data(as_text=True).lower()


def test_json_progress_update_with_csrf(client):
    book = create_book(client)
    token = csrf_from(client, f"/books/{book.id}")

    response = client.post(
        f"/books/{book.id}/progress",
        json={"page": 260, "csrf_token": token},
        headers={"X-CSRFToken": token},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["page"] == 260
    assert data["percent"] == 83.9
    assert data["width"] == 83.9

    db.session.refresh(book)
    assert book.current_page == 260
    assert ReadingSession.query.count() == 1


def test_json_progress_update_requires_valid_csrf(client):
    book = create_book(client)
    response = client.post(
        f"/books/{book.id}/progress",
        json={"page": 100, "csrf_token": "invalid"},
    )
    assert response.status_code == 400
    assert response.get_json()["ok"] is False
    db.session.refresh(book)
    assert book.current_page == 20


def test_unknown_page_count_tracks_page_without_percentage(client):
    book = create_book(client, page_count="", current_page="0")
    response = client.post(
        f"/books/{book.id}/progress", data={"page": "88"}, follow_redirects=True
    )
    db.session.refresh(book)
    assert book.page_count is None
    assert book.current_page == 88
    assert book.progress_percent is None
    assert book.progress_width == 0
    assert "Page 88" in response.get_data(as_text=True)


def test_same_page_and_backwards_updates_do_not_create_sessions(client):
    book = create_book(client)
    client.post(f"/books/{book.id}/progress", data={"page": "100"})
    client.post(f"/books/{book.id}/progress", data={"page": "100"})
    client.post(f"/books/{book.id}/progress", data={"page": "60"})
    assert [session.page for session in ReadingSession.query.all()] == [100]


def test_updating_page_moves_book_into_currently_reading(client):
    book = create_book(client, status=BookStatus.WANT_TO_READ, current_page="0")
    client.post(f"/books/{book.id}/progress", data={"page": "15"})
    db.session.refresh(book)
    assert book.status == BookStatus.CURRENTLY_READING
    assert book.date_started is not None


def test_completion_records_date_rating_and_final_session(client):
    book = create_book(client)
    response = client.post(
        f"/books/{book.id}/complete",
        data={"date_finished": "2026-05-04", "rating": "5"},
        follow_redirects=True,
    )
    db.session.refresh(book)
    assert book.status == BookStatus.FINISHED
    assert book.date_finished.isoformat() == "2026-05-04"
    assert book.current_page == 310
    assert book.rating == 5
    assert book.progress_width == 100
    assert ReadingSession.query.count() == 1
    assert "is finished" in response.get_data(as_text=True)
