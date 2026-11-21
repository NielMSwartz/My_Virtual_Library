"""Reading statistics derived from stored books and dated page snapshots."""

from __future__ import annotations

from collections import Counter
from datetime import date

from app.models import Book, BookStatus, Setting


def current_year() -> int:
    return date.today().year


def yearly_goal() -> int:
    return Setting.get_int("reading_goal", 0)


def goal_percent(completed: int, goal: int) -> float | None:
    if goal <= 0:
        return None
    return round(min(100.0, completed / goal * 100), 1)


def build_statistics() -> dict:
    """Calculate all dashboard and statistics figures from the database."""
    books = Book.query.all()
    year = current_year()

    counts = {status: 0 for status, _label in BookStatus.CHOICES}
    for book in books:
        counts[book.status] = counts.get(book.status, 0) + 1

    finished = [book for book in books if book.status == BookStatus.FINISHED]
    finished_this_year = [
        book
        for book in finished
        if book.date_finished and book.date_finished.year == year
    ]
    rated = [book.rating for book in books if book.rating is not None]
    average_rating = round(sum(rated) / len(rated), 1) if rated else None

    total_pages_read = 0
    pages_this_year = 0
    for book in books:
        sessions = sorted(book.sessions, key=lambda session: session.recorded_at)
        highest_page = max([session.page for session in sessions] or [book.current_page or 0])
        if book.status == BookStatus.FINISHED and book.page_count:
            highest_page = max(highest_page, book.page_count)
        total_pages_read += highest_page

        if sessions:
            previous = 0
            for session in sessions:
                delta = max(0, session.page - previous)
                if session.recorded_at.year == year:
                    pages_this_year += delta
                previous = max(previous, session.page)
        elif book.date_finished and book.date_finished.year == year and book.page_count:
            pages_this_year += book.page_count
        elif book.date_started and book.date_started.year == year:
            pages_this_year += book.current_page or 0

    completed_by_month = Counter(book.date_finished.month for book in finished_this_year)
    genres = Counter(book.genre.strip() for book in books if book.genre and book.genre.strip())

    reading_books = [
        book for book in books if book.status == BookStatus.CURRENTLY_READING
    ]
    measurable = [book.progress_percent for book in reading_books if book.progress_percent is not None]
    average_progress = round(sum(measurable) / len(measurable), 1) if measurable else None

    goal = yearly_goal()
    return {
        "total_books": len(books),
        "counts": counts,
        "total_finished": len(finished),
        "finished_this_year": len(finished_this_year),
        "total_pages_read": total_pages_read,
        "pages_this_year": pages_this_year,
        "average_rating": average_rating,
        "completed_by_month": completed_by_month,
        "genres": genres,
        "reading_books": reading_books,
        "average_progress": average_progress,
        "goal": goal,
        "goal_percent": goal_percent(len(finished_this_year), goal),
        "recently_finished": sorted(
            finished,
            key=lambda book: (book.date_finished or date.min, book.updated_at),
            reverse=True,
        )[:6],
        "recently_updated": sorted(books, key=lambda book: book.updated_at, reverse=True)[:6],
    }
