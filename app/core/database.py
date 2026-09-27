"""SQLite storage for the reading library: books, notes, and bookmarks.

Identity model
--------------
A book is identified by ``(content_hash, hash_algo)`` -- the digest of the PDF's
bytes -- and never by its path. ``book_locations`` records the paths a book has
been seen at, so renaming or moving a file keeps its notes and bookmarks
attached. Two copies of the same PDF are therefore one book, on purpose.

Storage layout
--------------
``<data_root>/library.db`` (SQLite) and ``<data_root>/notes/<book-hash>/note-<uuid>.md``
(Markdown bodies). The database stores note *metadata*; the prose lives in the
Markdown files so it stays editable in any editor and versionable with git.
``notes.file_path`` is always relative to the notes root -- never absolute.

Connections
-----------
No connection is held open. This is a single-user desktop app whose writes are
tiny, so every operation opens, runs, and closes its own connection. That keeps
``PRAGMA foreign_keys = ON`` (per-connection state, not a property of the file)
trivially true and leaves no long-lived handle for a crash to strand.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.hashing import DEFAULT_ALGORITHM, content_hash

# Must match the trailing ``PRAGMA user_version`` in ``schema.sql``.
SCHEMA_VERSION = 1
SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# ``CURRENT_TIMESTAMP`` in SQLite renders exactly this, so timestamps written by
# the application and by column defaults sort together as text.
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Shown to the user when the library had to fall back to a throwaway directory.
TEMPORARY_MODE_MESSAGE = (
    "Notes and bookmarks cannot be saved in this environment. Running in temporary mode."
)


class StorageError(RuntimeError):
    """Raised when the library cannot be created, opened, or written."""


class SchemaVersionError(StorageError):
    """Raised when the database on disk is newer than this build understands."""


@dataclass(frozen=True)
class Book:
    """One PDF, identified by the hash of its bytes."""

    id: int
    content_hash: str
    hash_algo: str
    size_bytes: int
    title: str | None
    author: str | None


@dataclass(frozen=True)
class Bookmark:
    """A reader's mark on a zero-based page of one book."""

    id: int
    book_id: int
    page: int
    label: str | None
    created_at: str


@dataclass(frozen=True)
class Note:
    """Metadata for one Markdown note whose body lives outside the database."""

    id: int
    uuid: str
    book_id: int
    file_path: str
    title: str | None
    page: int | None
    anchor_text: str | None
    created_at: str
    updated_at: str


def default_data_root() -> Path:
    """Return the XDG data directory owned by this application."""
    data_home = os.environ.get("XDG_DATA_HOME")
    base_directory = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return base_directory / "linux-pdf-reader"


def timestamp_now() -> str:
    """Return the current UTC time in SQLite's ``CURRENT_TIMESTAMP`` format."""
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FORMAT)


def _file_timestamp(file_stat: os.stat_result) -> str:
    """Render a file's mtime in the same format as every other timestamp."""
    return datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc).strftime(TIMESTAMP_FORMAT)


def derive_note_title(body: str) -> str | None:
    """Return a note's first non-empty line as its title, or ``None`` when blank.

    A leading Markdown heading marker is dropped, so ``# Chapter two`` becomes
    ``Chapter two``. The title is what the notes list shows, which is why it is
    derived from the body rather than typed separately.
    """
    for line in body.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return None


def open_library(preferred_root: Path | None = None) -> tuple["Database", str | None]:
    """Return a usable library, degrading to a temporary one when needed.

    A reader must still open a PDF on a locked-down machine, a read-only home, or
    a full disk, so a failed initialisation falls back to a throwaway directory
    under the system temp folder instead of aborting the launch. The second value
    is the message to show the user, or ``None`` when the preferred location
    worked; the reason itself is kept on ``Database.temporary_reason``.
    """
    try:
        database = Database(preferred_root)
        database.initialize()
        return database, None
    except StorageError as error:
        temporary_root = Path(tempfile.mkdtemp(prefix="fallow-library-"))
        database = Database(temporary_root, temporary=True)
        database.initialize()
        database.temporary_reason = str(error)
        return database, TEMPORARY_MODE_MESSAGE


class Database:
    """Own the SQLite file, the notes directory, and every query against them."""

    def __init__(self, data_root: Path | None = None, temporary: bool = False) -> None:
        """Point the store at ``data_root`` (defaults to the XDG data directory)."""
        self.data_root = (data_root or default_data_root()).expanduser()
        self.db_path = self.data_root / "library.db"
        self.notes_root = self.data_root / "notes"
        # ``True`` for the throwaway store ``open_library`` falls back to when the
        # configured folder cannot be written; its contents are gone at exit.
        self.temporary = temporary
        self.temporary_reason: str | None = None
        # (path, mtime_ns, size) -> book id, so hashing happens once per file
        # rather than once per tab switch.
        self._book_id_cache: dict[tuple[str, int, int], int] = {}

    # -- schema ----------------------------------------------------------------

    def initialize(self) -> None:
        """Create the data directories and apply ``schema.sql`` exactly once.

        ``PRAGMA user_version`` is the guard: ``0`` means the file is brand new
        (or a previous run never finished its script), so the script is executed;
        any other version means the schema is already in place and must not be
        re-applied, because re-running it would fail on the existing tables.

        Raises:
            StorageError: when the folder cannot be created or the file cannot be
                opened or written. :func:`open_library` catches this to degrade
                to a temporary library instead of aborting the launch.
            SchemaVersionError: when the file belongs to a newer build.
        """
        try:
            self.data_root.mkdir(parents=True, exist_ok=True)
            self.notes_root.mkdir(parents=True, exist_ok=True)
            connection = self.connect()
            try:
                version = self.schema_version(connection)
                if version == SCHEMA_VERSION:
                    return
                if version > SCHEMA_VERSION:
                    raise SchemaVersionError(
                        f"{self.db_path} uses schema version {version}, "
                        f"but this build only understands {SCHEMA_VERSION}"
                    )
                connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
                connection.commit()
            finally:
                connection.close()
        except (OSError, sqlite3.Error) as error:
            raise StorageError(f"Cannot use the library at {self.data_root}: {error}") from error

    def connect(self) -> sqlite3.Connection:
        """Open a connection with foreign keys enforced.

        ``PRAGMA foreign_keys`` is per-connection state rather than a property of
        the file, so it is set here on every connection; otherwise the
        ``ON DELETE CASCADE`` rules silently do nothing.
        """
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def schema_version(connection: sqlite3.Connection) -> int:
        """Return ``PRAGMA user_version`` of an already-open connection."""
        row = connection.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row is not None else 0

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection for a read-only block and always close it."""
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection inside one transaction, rolling back on failure."""
        connection = self.connect()
        try:
            with connection:  # commits on success, rolls back on an exception
                yield connection
        finally:
            connection.close()

    # -- books -----------------------------------------------------------------

    def ensure_book(
        self,
        file_path: Path,
        title: str | None = None,
        author: str | None = None,
        algorithm: str = DEFAULT_ALGORITHM,
    ) -> int:
        """Register a file and return the id of the book whose bytes it holds.

        The digest is of the file's contents, so a moved or renamed PDF (and any
        copy of it) resolves to the same book -- and therefore to the same notes
        and bookmarks. Repeated calls for an unchanged file are answered from a
        path/mtime/size cache, so a document is hashed once, not on every tab
        switch.
        """
        file_stat = file_path.stat()
        cache_key = (str(file_path), file_stat.st_mtime_ns, file_stat.st_size)
        cached_book_id = self._book_id_cache.get(cache_key)
        if cached_book_id is not None:
            return cached_book_id

        digest = content_hash(file_path, algorithm)
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT id FROM books WHERE content_hash = ? AND hash_algo = ?",
                (digest, algorithm),
            ).fetchone()
            if row is None:
                cursor = connection.execute(
                    "INSERT INTO books (content_hash, hash_algo, size_bytes, title, author, last_opened_at)"
                    " VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    (digest, algorithm, file_stat.st_size, title, author),
                )
                book_id = int(cursor.lastrowid or 0)
            else:
                book_id = int(row["id"])
                connection.execute(
                    "UPDATE books SET size_bytes = ?,"
                    " title = COALESCE(?, title), author = COALESCE(?, author),"
                    " last_opened_at = CURRENT_TIMESTAMP"
                    " WHERE id = ?",
                    (file_stat.st_size, title, author, book_id),
                )
            self._record_location(connection, book_id, file_path)

        self._book_id_cache[cache_key] = book_id
        return book_id

    @staticmethod
    def _record_location(connection: sqlite3.Connection, book_id: int, file_path: Path) -> None:
        """Add a path hint for a book while keeping exactly one primary location.

        The first path a book is seen at becomes the primary one; later paths are
        hints, because the partial unique index allows only one primary row.
        """
        has_primary = (
            connection.execute(
                "SELECT 1 FROM book_locations WHERE book_id = ? AND is_primary = 1",
                (book_id,),
            ).fetchone()
            is not None
        )
        connection.execute(
            "INSERT OR IGNORE INTO book_locations (book_id, path, is_primary) VALUES (?, ?, ?)",
            (book_id, str(file_path), 0 if has_primary else 1),
        )
        connection.execute(
            "UPDATE book_locations SET last_seen_at = CURRENT_TIMESTAMP WHERE book_id = ? AND path = ?",
            (book_id, str(file_path)),
        )

    def book(self, book_id: int) -> Book | None:
        """Return one book, or ``None`` when the id is unknown."""
        with self.read() as connection:
            row = connection.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return self._to_book(row) if row is not None else None

    def find_book(self, content_hash_value: str, algorithm: str = DEFAULT_ALGORITHM) -> Book | None:
        """Return the book with this content hash, if it has been seen before."""
        with self.read() as connection:
            row = connection.execute(
                "SELECT * FROM books WHERE content_hash = ? AND hash_algo = ?",
                (content_hash_value, algorithm),
            ).fetchone()
        return self._to_book(row) if row is not None else None

    def books(self) -> list[Book]:
        """Return every known book, most recently opened first."""
        with self.read() as connection:
            rows = connection.execute(
                "SELECT * FROM books ORDER BY last_opened_at IS NULL, last_opened_at DESC, id"
            ).fetchall()
        return [self._to_book(row) for row in rows]

    def locations(self, book_id: int) -> list[str]:
        """Return every path this book has been seen at, primary first."""
        with self.read() as connection:
            rows = connection.execute(
                "SELECT path FROM book_locations WHERE book_id = ? ORDER BY is_primary DESC, id",
                (book_id,),
            ).fetchall()
        return [str(row["path"]) for row in rows]

    def primary_location(self, book_id: int) -> str | None:
        """Return the path this book is primarily read from, if one is recorded."""
        with self.read() as connection:
            row = connection.execute(
                "SELECT path FROM book_locations WHERE book_id = ? AND is_primary = 1",
                (book_id,),
            ).fetchone()
        return str(row["path"]) if row is not None else None

    def delete_book(self, book_id: int, remove_notes: bool = True) -> None:
        """Delete a book with its locations and marks, and by default its notes.

        Deleting the book row cascades to ``book_locations``, ``notes``,
        ``note_tags``, and ``bookmarks``. The Markdown bodies are not covered by
        that cascade, so the book's notes directory is removed here; passing
        ``remove_notes=False`` instead documents the files as intentionally
        orphaned on disk.
        """
        book = self.book(book_id)
        if book is None:
            return
        with self.transaction() as connection:
            connection.execute("DELETE FROM books WHERE id = ?", (book_id,))
        self._book_id_cache = {
            key: value for key, value in self._book_id_cache.items() if value != book_id
        }
        if remove_notes:
            shutil.rmtree(self.book_directory(book.content_hash), ignore_errors=True)

    def book_directory(self, content_hash_value: str) -> Path:
        """Return the directory that holds one book's note files."""
        if not content_hash_value.isalnum():
            raise ValueError(f"Refusing to use an unsafe book directory name: {content_hash_value!r}")
        return self.notes_root / content_hash_value

    # -- notes -----------------------------------------------------------------

    def create_note(
        self,
        book_id: int,
        body: str = "",
        title: str | None = None,
        page: int | None = None,
        anchor_text: str | None = None,
    ) -> Note:
        """Write a new Markdown file and record it in the book's directory."""
        book = self.book(book_id)
        if book is None:
            raise ValueError(f"No book with id {book_id}")
        note_uuid = str(uuid.uuid4())
        relative_path = f"{book.content_hash}/note-{note_uuid}.md"
        absolute_path = self.note_file_path(relative_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_text(body, encoding="utf-8")
        file_stat = absolute_path.stat()
        now = timestamp_now()
        with self.transaction() as connection:
            cursor = connection.execute(
                "INSERT INTO notes (uuid, book_id, file_path, title, page, anchor_text,"
                " created_at, updated_at, file_mtime, file_size)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    note_uuid,
                    book_id,
                    relative_path,
                    title,
                    page,
                    anchor_text,
                    now,
                    now,
                    _file_timestamp(file_stat),
                    file_stat.st_size,
                ),
            )
            note_id = int(cursor.lastrowid or 0)
        return Note(
            id=note_id,
            uuid=note_uuid,
            book_id=book_id,
            file_path=relative_path,
            title=title,
            page=page,
            anchor_text=anchor_text,
            created_at=now,
            updated_at=now,
        )

    def note(self, note_id: int) -> Note | None:
        """Return one note's metadata, or ``None`` when the id is unknown."""
        with self.read() as connection:
            row = connection.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return self._to_note(row) if row is not None else None

    def notes_for_book(self, book_id: int) -> list[Note]:
        """Return one book's notes, ordered by page and then creation time."""
        with self.read() as connection:
            rows = connection.execute(
                "SELECT * FROM notes WHERE book_id = ? ORDER BY page IS NULL, page, created_at",
                (book_id,),
            ).fetchall()
        return [self._to_note(row) for row in rows]

    def read_note_body(self, note_id: int) -> str | None:
        """Return a note's Markdown, or ``None`` when the row or file is gone."""
        note = self.note(note_id)
        if note is None:
            return None
        try:
            return self.note_file_path(note.file_path).read_text(encoding="utf-8")
        except OSError:
            return None

    def update_note_body(self, note_id: int, body: str) -> Note | None:
        """Rewrite a note's Markdown and refresh its metadata in the same call.

        ``updated_at`` and the title (derived from the body's first line, so the
        notes list always matches what the note says) are written here rather
        than by a trigger, so every write path is explicit and centralised in
        this module.
        """
        note = self.note(note_id)
        if note is None:
            return None
        absolute_path = self.note_file_path(note.file_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_text(body, encoding="utf-8")
        file_stat = absolute_path.stat()
        with self.transaction() as connection:
            connection.execute(
                "UPDATE notes SET updated_at = ?, title = ?, file_mtime = ?, file_size = ? WHERE id = ?",
                (
                    timestamp_now(),
                    derive_note_title(body),
                    _file_timestamp(file_stat),
                    file_stat.st_size,
                    note_id,
                ),
            )
        return self.note(note_id)

    def reassign_note_book(self, note_id: int, new_book_id: int) -> Note | None:
        """Move a note -- file and row -- onto another book.

        SQLite cannot make a filesystem rename atomic with a row update, so the
        move happens first and is undone when the ``UPDATE`` fails: either both
        the file and ``file_path`` land on the new book, or neither does.
        """
        note = self.note(note_id)
        new_book = self.book(new_book_id)
        if note is None or new_book is None:
            return None

        old_absolute_path = self.note_file_path(note.file_path)
        new_relative_path = f"{new_book.content_hash}/note-{note.uuid}.md"
        new_absolute_path = self.note_file_path(new_relative_path)
        new_absolute_path.parent.mkdir(parents=True, exist_ok=True)
        moved = old_absolute_path != new_absolute_path and old_absolute_path.exists()
        if moved:
            shutil.move(str(old_absolute_path), str(new_absolute_path))

        try:
            file_stat = new_absolute_path.stat() if new_absolute_path.exists() else None
            with self.transaction() as connection:
                connection.execute(
                    "UPDATE notes SET book_id = ?, file_path = ?, updated_at = ?,"
                    " file_mtime = ?, file_size = ?"
                    " WHERE id = ?",
                    (
                        new_book_id,
                        new_relative_path,
                        timestamp_now(),
                        _file_timestamp(file_stat) if file_stat is not None else None,
                        file_stat.st_size if file_stat is not None else None,
                        note_id,
                    ),
                )
        except Exception:
            if moved:
                shutil.move(str(new_absolute_path), str(old_absolute_path))
            raise

        self._remove_directory_if_empty(Path(note.file_path).parent)
        return self.note(note_id)

    def delete_note(self, note_id: int) -> bool:
        """Remove a note's row and its Markdown file, pruning an empty book dir."""
        note = self.note(note_id)
        if note is None:
            return False
        with self.transaction() as connection:
            connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self._remove_file(self.note_file_path(note.file_path))
        self._remove_directory_if_empty(Path(note.file_path).parent)
        return True

    def note_file_path(self, relative_path: str) -> Path:
        """Resolve a note's stored path against the notes root.

        ``notes.file_path`` is relative by invariant; an absolute value would
        escape the notes root, so it is rejected rather than resolved.
        """
        stored_path = Path(relative_path)
        if stored_path.is_absolute():
            raise ValueError(f"Note path must be relative to the notes root: {relative_path!r}")
        return self.notes_root / stored_path

    @staticmethod
    def _remove_file(file_path: Path) -> None:
        """Best-effort delete: a missing or locked file must not fail cleanup."""
        try:
            file_path.unlink()
        except OSError:
            pass

    def _remove_directory_if_empty(self, relative_directory: Path) -> None:
        """Delete a book's notes directory once its last note has gone."""
        if relative_directory == Path(".") or relative_directory.is_absolute():
            return
        try:
            (self.notes_root / relative_directory).rmdir()  # succeeds only when empty
        except OSError:
            pass

    # -- bookmarks -------------------------------------------------------------

    def bookmarks(self, book_id: int) -> list[Bookmark]:
        """Return one book's marks, ordered by page."""
        with self.read() as connection:
            rows = connection.execute(
                "SELECT * FROM bookmarks WHERE book_id = ? ORDER BY page",
                (book_id,),
            ).fetchall()
        return [self._to_bookmark(row) for row in rows]

    def bookmarked_pages(self, book_id: int) -> list[int]:
        """Return the marked pages of a book as zero-based numbers, in order."""
        return [bookmark.page for bookmark in self.bookmarks(book_id)]

    def bookmark_count(self, book_id: int) -> int:
        """Return how many pages of a book are marked."""
        with self.read() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM bookmarks WHERE book_id = ?", (book_id,)
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def is_bookmarked(self, book_id: int, page: int) -> bool:
        """Report whether a page of a book already carries a mark."""
        with self.read() as connection:
            row = connection.execute(
                "SELECT 1 FROM bookmarks WHERE book_id = ? AND page = ?",
                (book_id, page),
            ).fetchone()
        return row is not None

    def add_bookmark(self, book_id: int, page: int, label: str | None = None) -> None:
        """Mark a page, replacing the label when one is supplied."""
        _validate_page(page)
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO bookmarks (book_id, page, label) VALUES (?, ?, ?)"
                " ON CONFLICT(book_id, page) DO UPDATE SET label = COALESCE(excluded.label, bookmarks.label)",
                (book_id, page, label),
            )

    def remove_bookmark(self, book_id: int, page: int) -> None:
        """Remove a page's mark; removing one that is not there does nothing."""
        with self.transaction() as connection:
            connection.execute(
                "DELETE FROM bookmarks WHERE book_id = ? AND page = ?",
                (book_id, page),
            )

    def toggle_bookmark(self, book_id: int, page: int, label: str | None = None) -> bool:
        """Add a page's mark, or remove it when present.

        Returns:
            ``True`` when the page ended up marked, ``False`` when it was unmarked.
        """
        if self.is_bookmarked(book_id, page):
            self.remove_bookmark(book_id, page)
            return False
        self.add_bookmark(book_id, page, label)
        return True

    # -- row mapping -----------------------------------------------------------

    @staticmethod
    def _to_book(row: sqlite3.Row) -> Book:
        return Book(
            id=int(row["id"]),
            content_hash=str(row["content_hash"]),
            hash_algo=str(row["hash_algo"]),
            size_bytes=int(row["size_bytes"]),
            title=row["title"],
            author=row["author"],
        )

    @staticmethod
    def _to_note(row: sqlite3.Row) -> Note:
        page = row["page"]
        return Note(
            id=int(row["id"]),
            uuid=str(row["uuid"]),
            book_id=int(row["book_id"]),
            file_path=str(row["file_path"]),
            title=row["title"],
            page=int(page) if page is not None else None,
            anchor_text=row["anchor_text"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _to_bookmark(row: sqlite3.Row) -> Bookmark:
        return Bookmark(
            id=int(row["id"]),
            book_id=int(row["book_id"]),
            page=int(row["page"]),
            label=row["label"],
            created_at=str(row["created_at"]),
        )


def _validate_page(page: int) -> None:
    """Reject a page number that cannot come from PyMuPDF's zero-based pages."""
    if page < 0:
        raise ValueError(f"Page numbers are zero-based and cannot be negative: {page}")
