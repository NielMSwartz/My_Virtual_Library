"""Statistics calculations and live dashboard/goal integration."""

from datetime import date, datetime

from app import db
from app.models import Book, BookStatus, ReadingSession, Setting
from app.services.reading_stats import build_statistics, goal_percent
from tests.test_books import book_payload

YEAR = date.today().year


def add_book(title, **kwargs):
    book = Book(
        title=title,
        authors=kwargs.pop("authors", "Test Author"),
        status=kwargs.pop("status", BookStatus.WANT_TO_READ),
        page_count=kwargs.pop("page_count", None),
        current_page=kwargs.pop("current_page", 0),
        rating=kwargs.pop("rating", None),
        genre=kwargs.pop("genre", None),
        date_started=kwargs.pop("date_started", None),
        date_finished=kwargs.pop("date_finished", None),
    )
    db.session.add(book)
    db.session.commit()
    return book


def add_session(book, page, month, day=1):
    db.session.add(
        ReadingSession(book_id=book.id, page=page, recorded_at=datetime(YEAR, month, day, 12, 0))
    )
    db.session.commit()


def test_statistics_use_real_book_and_session_data(app):
    finished = add_book(
        "Finished Book",
        status=BookStatus.FINISHED,
        page_count=300,
        current_page=300,
        rating=5,
        genre="Fantasy",
        date_finished=date(YEAR, 2, 14),
    )
    add_session(finished, 100, 1)
    add_session(finished, 300, 2, 14)

    reading = add_book(
        "In Progress",
        status=BookStatus.CURRENTLY_READING,
        page_count=200,
        current_page=100,
        rating=3,
        genre="Fantasy",
    )
    add_session(reading, 100, 3)

    add_book("Unread Book", genre="History")

    stats = build_statistics()
    assert stats["total_books"] == 3
    assert stats["counts"][BookStatus.FINISHED] == 1
    assert stats["counts"][BookStatus.CURRENTLY_READING] == 1
    assert stats["total_finished"] == 1
    assert stats["finished_this_year"] == 1
    assert stats["average_rating"] == 4.0
    assert stats["total_pages_read"] == 400
    assert stats["pages_this_year"] == 400
    assert stats["completed_by_month"][2] == 1
    assert stats["genres"]["Fantasy"] == 2
    assert stats["average_progress"] == 50.0


def test_repeated_snapshots_do_not_inflate_pages_read(app):
    book = add_book("Steady Reader", status=BookStatus.CURRENTLY_READING, page_count=100)
    add_session(book, 50, 1)
    add_session(book, 50, 2)
    add_session(book, 100, 3)

    stats = build_statistics()
    assert stats["pages_this_year"] == 100
    assert stats["total_pages_read"] == 100


def test_goal_progress_helper():
    assert goal_percent(6, 24) == 25.0
    assert goal_percent(30, 24) == 100.0
    assert goal_percent(5, 0) is None


def test_dashboard_and_statistics_pages_reflect_database(client):
    client.post("/books/new", data=book_payload(status=BookStatus.FINISHED, rating="4"))
    client.post(
        "/settings/",
        data={"yearly_goal": "12"},
        follow_redirects=True,
    )

    dashboard = client.get("/").get_data(as_text=True)
    assert 'stat-value">1</span>' in dashboard
    assert "Books in library" in dashboard

    stats_html = client.get("/statistics/").get_data(as_text=True)
    assert "/ 12 books" in stats_html
    assert "Books finished" in client.get("/statistics/").get_data(as_text=True)


def test_saving_goal_persists_in_settings_table(client):
    response = client.post("/settings/", data={"yearly_goal": "24"}, follow_redirects=True)
    assert response.status_code == 200
    db.session.remove()
    assert Setting.get_int("reading_goal") == 24
    assert "Reading goal saved" in response.get_data(as_text=True)


def test_statistics_page_renders_empty_library(client):
    response = client.get("/statistics/")
    assert response.status_code == 200
    assert "Books completed by month" in response.get_data(as_text=True)
