"""Core CRUD, filtering and status-change tests."""

from datetime import date

from app import db
from app.models import Book, BookStatus, ReadingSession


def book_payload(**overrides):
    payload = {
        "title": "The Hobbit",
        "authors": "J.R.R. Tolkien",
        "status": BookStatus.WANT_TO_READ,
        "page_count": "310",
        "current_page": "0",
        "genre": "Fantasy",
        "rating": "0",
        "purchase_status": "owned",
        "currency": "USD",
        "source": "manual",
    }
    payload.update(overrides)
    return payload


def test_create_book_via_form_persists_and_redirects(client):
    response = client.post("/books/new", data=book_payload(), follow_redirects=True)
    assert response.status_code == 200

    book = Book.query.one()
    assert book.title == "The Hobbit"
    assert book.authors == "J.R.R. Tolkien"
    assert book.page_count == 310
    assert book.status == BookStatus.WANT_TO_READ
    assert "was added to your shelf" in response.get_data(as_text=True)


def test_book_detail_page_renders(client):
    client.post("/books/new", data=book_payload())
    book = Book.query.one()
    response = client.get(f"/books/{book.id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "The Hobbit" in html
    assert "Reading progress" in html
    assert "Save page" in html


def test_edit_book_updates_existing_record(client):
    client.post("/books/new", data=book_payload())
    book = Book.query.one()

    response = client.post(
        f"/books/{book.id}/edit",
        data=book_payload(title="The Hobbit (Revised)", genre="High Fantasy", rating="5"),
        follow_redirects=True,
    )
    assert response.status_code == 200
    db.session.refresh(book)
    assert Book.query.count() == 1
    assert book.title == "The Hobbit (Revised)"
    assert book.genre == "High Fantasy"
    assert book.rating == 5


def test_delete_book_removes_book_and_sessions(client):
    client.post(
        "/books/new",
        data=book_payload(status=BookStatus.CURRENTLY_READING, current_page="80"),
    )
    book = Book.query.one()
    db.session.add(ReadingSession(book_id=book.id, page=80))
    db.session.commit()

    response = client.post(f"/books/{book.id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert Book.query.count() == 0
    assert ReadingSession.query.count() == 0


def test_duplicate_isbn_is_rejected(client):
    client.post("/books/new", data=book_payload(isbn="9780261103344"))
    response = client.post(
        "/books/new",
        data=book_payload(title="Hobbit, The", isbn="978-0-261-10334-4"),
    )
    assert response.status_code == 200
    assert "already in your library" in response.get_data(as_text=True)
    assert Book.query.count() == 1


def test_duplicate_title_and_author_is_rejected(client):
    client.post("/books/new", data=book_payload())
    response = client.post("/books/new", data=book_payload(title="  the   hobbit  "))
    assert "already in your library" in response.get_data(as_text=True)
    assert Book.query.count() == 1


def test_editing_same_book_does_not_trigger_duplicate_guard(client):
    client.post("/books/new", data=book_payload())
    book = Book.query.one()
    response = client.post(
        f"/books/{book.id}/edit",
        data=book_payload(notes="A present from Dad."),
        follow_redirects=True,
    )
    assert response.status_code == 200
    db.session.refresh(book)
    assert book.notes == "A present from Dad."


def test_current_page_cannot_exceed_page_count(client):
    response = client.post(
        "/books/new",
        data=book_payload(current_page="400"),
    )
    assert "cannot be greater than the total page count" in response.get_data(as_text=True)
    assert Book.query.count() == 0


def test_status_change_sets_dates_and_completion(client):
    client.post("/books/new", data=book_payload())
    book = Book.query.one()

    client.post(f"/books/{book.id}/status", data={"status": BookStatus.CURRENTLY_READING})
    db.session.refresh(book)
    assert book.date_started == date.today()

    client.post(f"/books/{book.id}/status", data={"status": BookStatus.FINISHED})
    db.session.refresh(book)
    assert book.date_finished == date.today()
    assert book.current_page == 310
    assert ReadingSession.query.count() == 1

    client.post(f"/books/{book.id}/status", data={"status": BookStatus.WANT_TO_READ})
    db.session.refresh(book)
    assert book.date_finished is None


def test_local_search_and_filters(client):
    client.post("/books/new", data=book_payload())
    client.post(
        "/books/new",
        data=book_payload(
            title="Dune",
            authors="Frank Herbert",
            isbn="9780441013593",
            genre="Sci-Fi",
            status=BookStatus.FINISHED,
            current_page="412",
            page_count="412",
        ),
    )

    assert "2 books shown" in client.get("/books/").get_data(as_text=True)

    search = client.get("/books/?q=tolkien").get_data(as_text=True)
    assert "The Hobbit" in search
    assert "Dune" not in search

    filtered = client.get("/books/?status=finished&genre=Sci-Fi").get_data(as_text=True)
    assert "Dune" in filtered
    assert "The Hobbit" not in filtered

    isbn_search = client.get("/books/?q=9780441013593").get_data(as_text=True)
    assert "Dune" in isbn_search
