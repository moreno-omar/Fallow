-- ============================================================
-- schema.sql
-- ============================================================
--
-- IDENTITY MODEL
--   A book is identified by (content_hash, hash_algo), NOT by path.
--   Paths are hints stored in book_locations. Move/rename the file
--   and the book — and its notes and bookmarks — follow.
--
-- CONTENT LOCATION
--   Note bodies live as external Markdown files under:
--       <notes_root>/<book_hash>/note-<uuid>.md
--   The DB stores metadata only: location, anchors, tags, timestamps.
--   This keeps notes editable in Obsidian/vim/any editor and
--   versionable with git.
--
-- PORTABILITY
--   Bookmarks and notes are APP-LOCAL (SQLite). They do not embed
--   into the PDF file. If future versions want PDF-native bookmarks,
--   that will be a separate feature.
--
-- SHARED NOTES
--   Two identical PDFs (same content hash) intentionally share the
--   same notes and bookmarks. This is the point of content-hash
--   identity. If you ever need per-file disambiguation, add a
--   secondary key to books (e.g. filename) and widen the identity.
--
-- MIGRATIONS
--   Schema version is stored in PRAGMA user_version. Bump it whenever
--   the schema changes and add a migration in app code. Never edit
--   this file for an existing install without a migration.
--
-- HOW THIS FILE IS RUN
--   ``Database.initialize()`` runs this script exactly once: only when
--   PRAGMA user_version is still 0. It is never executed against a
--   database that already carries a schema version.
--   The DDL is wrapped in one transaction and PRAGMA user_version is the
--   last statement, so a failed run leaves user_version at 0 and can be
--   retried instead of leaving a half-created schema behind.
--   ``PRAGMA foreign_keys`` is deliberately NOT here: it is per-connection
--   state, so Database.connect() sets it on every connection.
--
-- INVARIANTS
--   - Exactly one book_locations row per book has is_primary = 1
--     (enforced by partial unique index below).
--   - notes.file_path is always relative to the notes root.
--   - notes.updated_at is maintained by the application on write.
--     (No trigger — we want writes to be explicit and centralized.)
--
-- ============================================================

PRAGMA journal_mode = WAL;      -- concurrent reads while writing
PRAGMA synchronous = NORMAL;    -- good balance for a desktop app

BEGIN;

-- ============================================================
-- Books: identified by content hash, not path
-- ============================================================
CREATE TABLE books (
    id             INTEGER PRIMARY KEY,
    content_hash   TEXT NOT NULL,
    hash_algo      TEXT NOT NULL DEFAULT 'blake2b'
                   CHECK (hash_algo IN ('blake2b','sha256')),
    size_bytes     INTEGER NOT NULL,
    title          TEXT,
    author         TEXT,
    added_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP,
    UNIQUE(content_hash, hash_algo)
);

CREATE INDEX idx_books_hash ON books(content_hash);

-- ============================================================
-- Book locations: a book may exist at several paths
-- ============================================================
CREATE TABLE book_locations (
    id           INTEGER PRIMARY KEY,
    book_id      INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    path         TEXT NOT NULL,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_primary   INTEGER NOT NULL DEFAULT 0
                 CHECK (is_primary IN (0, 1)),
    UNIQUE(book_id, path)
);

CREATE INDEX idx_book_locations_book ON book_locations(book_id);

-- Exactly one primary location per book.
CREATE UNIQUE INDEX idx_book_locations_one_primary
    ON book_locations(book_id)
    WHERE is_primary = 1;

-- ============================================================
-- Notes: body lives in an external .md file; DB stores metadata
-- ============================================================
CREATE TABLE notes (
    id          INTEGER PRIMARY KEY,
    uuid        TEXT NOT NULL,                 -- filename stem of the .md
    book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,

    -- RELATIVE to the notes root (<data_root>/notes/).
    -- Example value: "<book-hash>/note-<uuid>.md"
    -- Full path = notes_root / file_path.
    -- Never store an absolute path.
    -- INVARIANT: if book_id changes, move the file and update file_path
    --            in the same transaction.
    file_path   TEXT NOT NULL,

    title       TEXT,                          -- optional; often first H1
    page        INTEGER,                       -- nullable, zero-based
    anchor_text TEXT,                          -- nullable (highlight anchor)

    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Change detection for external edits.
    file_mtime  TIMESTAMP,
    file_size   INTEGER,

    UNIQUE(book_id, uuid)
);

CREATE INDEX idx_notes_book      ON notes(book_id);
CREATE INDEX idx_notes_book_page ON notes(book_id, page);

-- ============================================================
-- Tags: Obsidian-style, hierarchical with "/"
--   #project, #project/book, #status/todo
-- ============================================================
CREATE TABLE tags (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,   -- WITHOUT leading '#', e.g. 'project/book'
    parent_id INTEGER REFERENCES tags(id) ON DELETE SET NULL,
    color     TEXT                    -- optional UI hint
);

CREATE INDEX idx_tags_name   ON tags(name);
CREATE INDEX idx_tags_parent ON tags(parent_id);

-- ============================================================
-- note_tags: many-to-many between notes and tags
-- source distinguishes inline `#tag` vs frontmatter `tags:` entries,
-- which lets re-parsing clean up only the tags it owns.
-- ============================================================
CREATE TABLE note_tags (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    source  TEXT NOT NULL DEFAULT 'inline'
            CHECK (source IN ('inline','frontmatter')),
    PRIMARY KEY (note_id, tag_id, source)
);

CREATE INDEX idx_note_tags_tag  ON note_tags(tag_id);
CREATE INDEX idx_note_tags_note ON note_tags(note_id);

-- ============================================================
-- Bookmarks: app-local, keyed by book (content hash identity)
--   page is zero-based, matching PyMuPDF and the session file.
-- ============================================================
CREATE TABLE bookmarks (
    id         INTEGER PRIMARY KEY,
    book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    page       INTEGER NOT NULL,
    label      TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- A page can be bookmarked only once per book.
    -- If you later want multiple labelled bookmarks per page,
    -- change this to UNIQUE(book_id, page, label).
    UNIQUE(book_id, page)
);

CREATE INDEX idx_bookmarks_book_page ON bookmarks(book_id, page);

-- The schema version is the last statement: it is the marker that tells
-- Database.initialize() the script has already been applied.
PRAGMA user_version = 1;

COMMIT;
