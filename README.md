# Bookshelf — Personal Book Tracker

A calm, single-user digital bookshelf built with Flask. Track what you are
reading, keep want-to-read and to-buy lists, save a digital bookmark for every
book, and see honest reading statistics — all stored in a real database.

## Features

- **Book management** — add, edit and delete books with covers, ISBN, publisher,
  year, pages, genre, rating, notes, review, purchase details and dates.
- **Online discovery** — search Google Books (no API key needed for normal use),
  with Open Library as a fallback. Pick a result to prefill the book form.
  Search results are cached on the server.
- **Duplicate protection** — checks normalised ISBN, then title + primary author.
- **Digital bookmark** — current page is saved per book with a progress bar and
  a ribbon on the cover. Quick updates can be made from cards and the dashboard
  without opening the book. Validation prevents negative or out-of-range pages.
- **Reading sessions** — dated page snapshots let the app calculate pages read
  without double-counting repeated updates to the same page.
- **Lists & filters** — Currently Reading, Want to Read, To Buy, Finished and All
  Books, with local search, status/genre/author/rating filters and sorting.
- **Dashboard & statistics** — live counts, continue-reading shortcuts, yearly
  goal, completed-books-by-month, genre distribution and per-book progress.
- **Polished UI** — responsive sidebar/bottom navigation, soft grey and sage
  palette, accessible form controls, modal delete confirmation and toast feedback.
- **Dark mode** — follows your device preference automatically, with a toggle in
  the top bar that remembers your choice.

## Quick start

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Create your local environment file (optional but recommended)
Copy-Item .env.example .env
# Edit .env and set a real SECRET_KEY

# 4. Apply database migrations
$env:FLASK_APP = "run.py"
flask db upgrade

# 5. Run the app
python run.py
```

Open <http://127.0.0.1:5000>. On a fresh database you will be asked to create
one private account (email + password). After signing in, the dashboard shows
an empty state and an **Add your first book** button.

## Install it on your phone and desktop

The app is a Progressive Web App (PWA). Once it is hosted on HTTPS, you can
install it so it opens in its own window with an app icon.

**Android (Chrome):** open the site → three-dot menu → **Install app** or
**Add to Home screen**.

**iPhone / iPad (Safari):** open the site → Share button → **Add to Home Screen**.

**Desktop (Chrome / Edge):** open the site → click the install icon in the
address bar, or use the browser menu → **Save and share → Install page as app**.

The app shell (styles, scripts and icons) is cached by a service worker, so the
interface still opens without a connection. Book data always comes from the
server, so changes need an internet connection. HTML pages are deliberately
never cached — that keeps CSRF tokens and your library fresh.

## Appearance

The theme follows your device setting by default. Use the sun/moon button in
the top bar to switch; your choice is saved in that browser and the site's
theme colour updates with it. Clearing site data resets it to the system
preference.

## Your private account

The bookshelf uses one email/password account. The sign-up page is only
available while no account exists; after that it redirects to sign-in. Passwords
are stored as salted hashes, never in plain text, and sessions use an HTTP-only,
SameSite cookie. Sign out from **Settings → Account**.

If you forget the password, reset it on the computer that can access the
database:

```powershell
flask reset-password --email you@example.com
# You will be prompted securely for the new password.
```

You can also create the first account without opening a browser:

```powershell
flask create-account --email you@example.com
```

The public PWA shell (`/offline`, `/sw.js`, `/manifest.webmanifest`) stays
available before sign-in so an installed app can still open while offline.
Everything else redirects to the sign-in page.

## Deploy to Render (free tier)

The repo includes a `render.yaml` Blueprint, so Render creates the web service
and Postgres database for you.

1. Push this repository to GitHub (see below if you have not pushed yet).
2. Create a free Render account at <https://dashboard.render.com/register>.
3. Go to <https://dashboard.render.com/select-repo?type=blueprint> and connect
   the `My_Virtual_Library` repository.
4. Render reads `render.yaml` and proposes a web service plus a Postgres
   database. Confirm the name and region (keep both in the same region).
5. Click **Apply**. The first deploy installs dependencies, runs
   `flask db upgrade` and starts Gunicorn.
6. Open the `onrender.com` URL shown on the service page. Create your private
   account on the first visit. Check the Logs tab if the first request fails.
7. Set your yearly reading goal in **Settings**.

**Important free-tier limits** (checked against Render's docs in November 2026):

- Free web services spin down after 15 minutes idle; the next visit takes about
  a minute to wake up.
- **Free Postgres expires 30 days after creation**, with a 14-day grace period.
  Upgrade the database to the $6/month plan before then or your data will be
  deleted. Paid plans also add backups.
- The free database is capped at 1 GB and has no backups. Export your data
  regularly if you rely on the free tier.
- Only one free Postgres database is allowed per Render workspace.

### Move your local books to Render

Signing in does **not** make data persist — the Render Postgres database does.
A new cloud database starts empty. To copy the books, bookmark history and
yearly goal from your local `instance/book_tracker.db`, use Render's **External
Database URL** from the database page:

```powershell
# 1. Point the Flask CLI at the Render database and apply the latest schema.
$env:DATABASE_URL = "postgresql://..."
$env:FLASK_APP = "run.py"
flask db upgrade

# 2. Copy local SQLite data into it. You will be prompted for the password.
python scripts/transfer_library.py --email you@example.com

Remove-Item Env:DATABASE_URL
```

If you already created your account on the website, leave out `--email`; the
script keeps the existing sign-in. If the Render database already contains
books, add `--force` and confirm the replacement. Do not use a database you
still need — `--force` deletes its books, sessions and goal before copying.

The free Postgres database is deleted 30 days after creation unless you upgrade
it. No login or migration script can prevent that; the $6/month plan is what
keeps your library permanently.

### Deploying updates

Commit and push to the connected branch. Render rebuilds automatically and runs
migrations before starting the new version. Keep `render.yaml` in sync if you
change the start command or environment variables.

## Configuration

All configuration is read from environment variables (or a local `.env` file).

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask session/CSRF signing key | development placeholder |
| `DATABASE_URL` | SQLAlchemy database URL (`postgres://` is normalised to `postgresql://`) | `sqlite:///<project>/instance/book_tracker.db` |
| `FLASK_CONFIG` | `config.DevelopmentConfig`, `config.TestingConfig` or `config.ProductionConfig` | `config.DevelopmentConfig` |
| `GOOGLE_BOOKS_API_KEY` | Optional higher-quota Google Books key | unset (basic search works without it) |
| `OPEN_LIBRARY_ENABLED` | Set to `0` to disable the fallback provider | `1` |
| `REQUEST_TIMEOUT` | Per-request timeout for external APIs (seconds) | `8` |
| `SEARCH_CACHE_TTL_SECONDS` | Search cache lifetime | `604800` (7 days) |

Never commit `.env` or the SQLite database in `instance/`.

## Database and migrations

The schema is managed with Flask-Migrate/Alembic:

```powershell
$env:FLASK_APP = "run.py"
flask db upgrade                # apply existing migrations
flask db migrate -m "message"   # generate a migration after model changes
flask db check                  # verify models match migrations
```

SQLite is the default. To migrate to PostgreSQL, install a driver such as
`psycopg[binary]`, set `DATABASE_URL` to a PostgreSQL URL and run
`flask db upgrade`. Column types and constraints are portable; the only
database-specific logic is avoided (progress sorting happens in Python).

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use an in-memory SQLite database and mock external HTTP calls, so they
never touch your real library or require network access. CSRF is disabled only
in the test configuration; the JSON bookmark endpoint still validates its CSRF
token explicitly.

## Project structure

```text
book_tracker/
  app/
    __init__.py            # app factory, extensions, auth guard, error handlers
    models.py              # User, Book, ReadingSession, Setting, SearchCache
    forms.py               # Flask-WTF forms and validation
    cli.py                 # create-account / reset-password commands
    routes/
      __init__.py          # blueprint registration
      auth.py              # sign-up, sign-in, sign-out, password change
      dashboard.py         # dashboard
      books.py             # CRUD, filters, status, progress, completion
      search.py            # external discovery JSON endpoint
      statistics.py        # statistics
      settings.py          # yearly goal
    services/
      google_books.py      # primary metadata provider
      open_library.py      # fallback provider
      metadata.py          # cached orchestration
      book_catalog.py      # duplicate detection
      reading_stats.py     # statistics calculations
    templates/             # Jinja2 templates and reusable macros
    static/
      css/style.css
      js/main.js           # navigation, modal, toasts, image fallback
      js/theme.js          # light/dark theme toggle
      js/reading_progress.js
      js/discovery.js
      sw.js                # offline shell service worker
      offline.html
      manifest.webmanifest
      images/icons/        # generated PWA icons
  migrations/              # Alembic migrations
  tests/
  scripts/generate_icons.py
  scripts/transfer_library.py  # one-time local SQLite → cloud copy
  instance/                # local SQLite database (git-ignored)
  config.py
  run.py
  render.yaml              # Render Blueprint
  requirements.txt
  .env.example
  .gitignore
```

## How statistics are calculated

- **Total pages read** is the highest page reached per book (from bookmark
  snapshots, falling back to the current page), summed once per book.
- **Pages read this year** sums the positive difference between consecutive
  dated snapshots that fall in the current year. Books without snapshots use
  their completion date (if finished) or start date (if started this year).
- Only books with `status = finished` count as completed. Reopening a finished
  book clears its completion date, so it stops counting toward the goal.
- Average rating uses all books that have a rating.

## Roadmap ideas

Optional future additions: multiple accounts, shared shelves, e-book file
imports, full data export, reading reminders, and email-based password reset.
