"""Book management: listing, filtering, creation, editing and deletion."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_wtf.csrf import validate_csrf
from sqlalchemy import func, or_
from wtforms.validators import ValidationError as CSRFValidationError

from app import db
from app.forms import BookForm, EmptyForm, ProgressForm, StatusForm
from app.models import Book, BookStatus, ReadingSession, normalize_isbn

books_bp = Blueprint("books", __name__, url_prefix="/books")

LIST_TITLES = {
    BookStatus.CURRENTLY_READING: "Currently Reading",
    BookStatus.WANT_TO_READ: "Want to Read",
    BookStatus.TO_BUY: "To Buy",
    BookStatus.FINISHED: "Finished Books",
}

SORT_LABELS = (
    ("recent_added", "Recently added"),
    ("recent_updated", "Recently updated"),
    ("title_az", "Title A–Z"),
    ("author_az", "Author A–Z"),
    ("progress", "Reading progress"),
    ("rating", "Highest rated"),
    ("recent_finished", "Recently finished"),
)

RATING_FILTERS = ((5, "5 stars"), (4, "4+ stars"), (3, "3+ stars"), (2, "2+ stars"), (1, "1+ stars"))

# Progress sorting is done in Python: the percentage is a model property and
# expressing it in SQL would require database-specific scalar functions.
SORT_EXPRESSIONS = {
    "recent_added": (Book.date_added.desc(), Book.id.desc()),
    "recent_updated": (Book.updated_at.desc(), Book.id.desc()),
    "title_az": (func.lower(Book.title).asc(),),
    "author_az": (func.lower(Book.authors).asc(),),
    "rating": (Book.rating.desc().nullslast(), Book.title.asc()),
    "recent_finished": (Book.date_finished.desc().nullslast(), Book.title.asc()),
}


def _like_pattern(value: str) -> str:
    """Escape LIKE wildcards so user input is treated literally."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _apply_form_to_book(form: BookForm, book: Book) -> None:
    """Copy validated form data onto a Book, including computed fields."""
    form.populate_obj(book)
    book.title = book.title.strip()
    book.authors = (book.authors or "").strip() or "Unknown author"
    book.isbn = (book.isbn or "").strip() or None
    book.isbn_normalized = normalize_isbn(book.isbn)
    book.current_page = book.current_page or 0
    book.rating = book.rating or None
    book.currency = (book.currency or "USD").upper()[:3]
    book.genre = (book.genre or "").strip() or None
    book.publisher = (book.publisher or "").strip() or None
    book.source = book.source or "manual"

    if book.status == BookStatus.CURRENTLY_READING and not book.date_started:
        book.date_started = date.today()
    if book.status == BookStatus.FINISHED and not book.date_finished:
        book.date_finished = date.today()


@books_bp.route("/")
def list_books():
    status = request.args.get("status", "").strip()
    query_text = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()
    author = request.args.get("author", "").strip()
    rating_raw = request.args.get("rating", "").strip()
    sort = request.args.get("sort", "recent_added").strip()

    books_query = Book.query
    if status in dict(BookStatus.CHOICES):
        books_query = books_query.filter(Book.status == status)
    if query_text:
        pattern = _like_pattern(query_text.lower())
        books_query = books_query.filter(
            or_(
                func.lower(Book.title).like(pattern, escape="\\"),
                func.lower(Book.authors).like(pattern, escape="\\"),
                func.lower(func.coalesce(Book.isbn, "")).like(pattern, escape="\\"),
            )
        )
    if genre:
        books_query = books_query.filter(func.lower(Book.genre) == genre.lower())
    if author:
        books_query = books_query.filter(func.lower(Book.authors).contains(author.lower(), autoescape=True))
    if rating_raw.isdigit():
        books_query = books_query.filter(Book.rating >= int(rating_raw))

    if sort == "progress":
        books = sorted(
            books_query.all(),
            key=lambda book: (book.progress_width, book.updated_at),
            reverse=True,
        )
    else:
        books = books_query.order_by(*SORT_EXPRESSIONS.get(sort, SORT_EXPRESSIONS["recent_added"])).all()

    genres = [
        row[0]
        for row in db.session.query(Book.genre)
        .filter(Book.genre.isnot(None), Book.genre != "")
        .distinct()
        .order_by(Book.genre)
        .all()
    ]
    authors = [
        row[0]
        for row in db.session.query(Book.authors)
        .filter(Book.authors.isnot(None), Book.authors != "")
        .distinct()
        .order_by(Book.authors)
        .all()
    ]

    return render_template(
        "books.html",
        books=books,
        list_title=LIST_TITLES.get(status, "All Books"),
        active_status=status,
        query_text=query_text,
        genre=genre,
        author=author,
        rating=rating_raw,
        sort=sort,
        genres=genres,
        authors=authors,
        sort_labels=SORT_LABELS,
        rating_filters=RATING_FILTERS,
        total_in_view=len(books),
    )


@books_bp.route("/new", methods=["GET", "POST"])
def new_book():
    form = BookForm()
    if form.validate_on_submit():
        book = Book()
        _apply_form_to_book(form, book)
        db.session.add(book)
        db.session.commit()
        flash(f'"{book.title}" was added to your shelf.', "success")
        return redirect(url_for("books.book_detail", book_id=book.id))
    return render_template("book_form.html", form=form, mode="create", book=None)


@books_bp.route("/<int:book_id>/edit", methods=["GET", "POST"])
def edit_book(book_id: int):
    book = db.session.get(Book, book_id)
    if book is None:
        abort(404)

    form = BookForm(obj=book)
    form.book_id = book.id
    if form.validate_on_submit():
        _apply_form_to_book(form, book)
        db.session.commit()
        flash("Book details saved.", "success")
        return redirect(url_for("books.book_detail", book_id=book.id))
    return render_template("book_form.html", form=form, mode="edit", book=book)


@books_bp.route("/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id: int):
    book = db.session.get(Book, book_id)
    if book is None:
        abort(404)
    form = EmptyForm()
    if not form.validate_on_submit():
        abort(400)
    title = book.title
    db.session.delete(book)
    db.session.commit()
    flash(f'"{title}" was removed from your shelf.', "success")
    return redirect(url_for("books.list_books"))


@books_bp.route("/<int:book_id>")
def book_detail(book_id: int):
    book = db.session.get(Book, book_id)
    if book is None:
        abort(404)
    status_form = StatusForm(status=book.status)
    progress_form = ProgressForm(page=book.current_page)
    progress_form.page_count = book.page_count
    delete_form = EmptyForm()
    return render_template(
        "book_detail.html",
        book=book,
        status_form=status_form,
        progress_form=progress_form,
        delete_form=delete_form,
        sessions=list(reversed(book.sessions[-5:])),
        today=date.today().isoformat(),
    )


def _record_progress(book: Book, new_page: int) -> None:
    """Persist a page snapshot, keeping the bookmark and dates consistent."""
    if book.page_count is not None:
        new_page = min(new_page, book.page_count)
    if new_page > book.current_page:
        db.session.add(ReadingSession(book_id=book.id, page=new_page))
    book.current_page = new_page
    if new_page > 0 and book.status in (BookStatus.WANT_TO_READ, BookStatus.TO_BUY):
        book.status = BookStatus.CURRENTLY_READING
    if book.status == BookStatus.CURRENTLY_READING and not book.date_started:
        book.date_started = date.today()


def _progress_message(book: Book) -> str:
    if book.page_count:
        return f"Bookmark saved — you're on page {book.current_page} of {book.page_count}."
    return f"Bookmark saved — you're on page {book.current_page}."


def _progress_payload(book: Book) -> dict:
    return {
        "ok": True,
        "book_id": book.id,
        "page": book.current_page,
        "page_count": book.page_count,
        "percent": book.progress_percent,
        "width": book.progress_width,
        "status": book.status,
        "status_label": book.status_label,
        "message": _progress_message(book),
    }


@books_bp.route("/<int:book_id>/progress", methods=["POST"])
def update_progress(book_id: int):
    book = db.session.get(Book, book_id)
    if book is None:
        abort(404)

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        try:
            validate_csrf(payload.get("csrf_token") or request.headers.get("X-CSRFToken"))
        except CSRFValidationError:
            return jsonify(ok=False, error="Your session expired. Refresh the page and try again."), 400

        try:
            new_page = int(payload.get("page"))
        except (TypeError, ValueError):
            return jsonify(ok=False, error="Enter a valid page number."), 400
        if new_page < 0:
            return jsonify(ok=False, error="Page cannot be negative."), 400
        if book.page_count is not None and new_page > book.page_count:
            return jsonify(ok=False, error="Page cannot be greater than the total page count."), 400

        _record_progress(book, new_page)
        db.session.commit()
        return jsonify(_progress_payload(book))

    form = ProgressForm()
    form.page_count = book.page_count
    if not form.validate_on_submit():
        for errors in form.errors.values():
            for error in errors:
                flash(error, "error")
        return redirect(url_for("books.book_detail", book_id=book.id))

    _record_progress(book, form.page.data)
    db.session.commit()
    flash(_progress_message(book), "success")
    return redirect(url_for("books.book_detail", book_id=book.id))


@books_bp.route("/<int:book_id>/complete", methods=["POST"])
def complete_book(book_id: int):
    book = db.session.get(Book, book_id)
    if book is None:
        abort(404)
    form = EmptyForm()
    if not form.validate_on_submit():
        abort(400)

    finished_raw = (request.form.get("date_finished") or "").strip()
    try:
        finished_on = date.fromisoformat(finished_raw) if finished_raw else date.today()
    except ValueError:
        flash("Enter a valid completion date.", "error")
        return redirect(url_for("books.book_detail", book_id=book.id))

    book.status = BookStatus.FINISHED
    book.date_finished = finished_on
    if not book.date_started and finished_on:
        book.date_started = finished_on
    rating_raw = (request.form.get("rating") or "").strip()
    if rating_raw.isdigit() and 1 <= int(rating_raw) <= 5:
        book.rating = int(rating_raw)
    if book.page_count and book.current_page < book.page_count:
        book.current_page = book.page_count
        db.session.add(ReadingSession(book_id=book.id, page=book.page_count))

    db.session.commit()
    flash(f'"{book.title}" is finished. Nice work!', "success")
    return redirect(url_for("books.book_detail", book_id=book.id))


@books_bp.route("/<int:book_id>/status", methods=["POST"])
def update_status(book_id: int):
    book = db.session.get(Book, book_id)
    if book is None:
        abort(404)
    form = StatusForm()
    if not form.validate_on_submit():
        abort(400)

    previous_status = book.status
    new_status = form.status.data
    book.status = new_status

    if new_status == BookStatus.CURRENTLY_READING and not book.date_started:
        book.date_started = date.today()

    if new_status == BookStatus.FINISHED:
        if not book.date_finished:
            book.date_finished = date.today()
        if book.page_count and book.current_page < book.page_count:
            book.current_page = book.page_count
            db.session.add(ReadingSession(book_id=book.id, page=book.page_count))
    elif previous_status == BookStatus.FINISHED:
        # Reopening a book means it should no longer count as completed.
        book.date_finished = None

    db.session.commit()
    flash(f"Moved to {BookStatus.LABELS[new_status]}.", "success")
    return redirect(url_for("books.book_detail", book_id=book.id))
