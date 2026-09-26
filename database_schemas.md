
## how relation should look

```text
~/.local/share/yourapp/
├── library.db                  # SQLite
└── notes/
    └── <book-hash>/
        ├── note-<uuid>.md      # the actual Markdown
        └── ...
```

## demo sqlite schema

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;      -- concurrent reads while writing
PRAGMA synchronous = NORMAL;    -- good balance for a desktop app

-- ============================================================
-- Books: identified by content hash, not path
-- ============================================================
CREATE TABLE books (
    id            INTEGER PRIMARY KEY,
    content_hash  TEXT NOT NULL UNIQUE,     -- e.g. blake2b hex of file bytes
    hash_algo     TEXT NOT NULL DEFAULT 'blake2b',
    size_bytes    INTEGER NOT NULL,
    title         TEXT,
    author        TEXT,
    -- Path is now just a "last known location" hint, not identity.
    -- Use book_locations to track multiple paths per book.
    added_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_opened_at TIMESTAMP
);

CREATE INDEX idx_books_hash ON books(content_hash);

-- A book may exist at several paths (copies, moves, symlinks).
-- Keep them all so we can find the file the user actually has.
CREATE TABLE book_locations (
    id          INTEGER PRIMARY KEY,
    book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    path        TEXT NOT NULL,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_primary  INTEGER NOT NULL DEFAULT 0,   -- which path to open by default
    UNIQUE(book_id, path)
);

CREATE INDEX idx_book_locations_book ON book_locations(book_id);

-- ============================================================
-- Notes: body lives in an external .md file; DB stores metadata
-- ============================================================
CREATE TABLE notes (
    id          INTEGER PRIMARY KEY,
    uuid        TEXT NOT NULL UNIQUE,         -- filename stem of the .md
    book_id     INTEGER REFERENCES books(id) ON DELETE CASCADE,
    -- relative to the notes root, e.g. "<book_hash>/note-<uuid>.md"
    file_path   TEXT NOT NULL,
    title       TEXT,                         -- optional; often the first H1
    page        INTEGER,                      -- nullable
    anchor_text TEXT,                         -- nullable (highlight anchor)
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- track file mtime so we can detect external edits
    file_mtime  TIMESTAMP
);

CREATE INDEX idx_notes_book ON notes(book_id);
CREATE INDEX idx_notes_book_page ON notes(book_id, page);

-- ============================================================
-- Tags: Obsidian-style, hierarchical with "/"
--   #project, #project/book, #status/todo
-- ============================================================
CREATE TABLE tags (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL UNIQUE,   -- stored WITHOUT leading '#'
                                      -- e.g. 'project/book'
    parent_id INTEGER REFERENCES tags(id) ON DELETE SET NULL,
    color     TEXT                    -- optional UI hint
);

CREATE INDEX idx_tags_name   ON tags(name);
CREATE INDEX idx_tags_parent ON tags(parent_id);

-- Many-to-many between notes and tags.
-- source distinguishes inline `#tag` vs frontmatter `tags:` entries,
-- which is useful for cleanup when a note is re-parsed.
CREATE TABLE note_tags (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    source  TEXT NOT NULL DEFAULT 'inline'
            CHECK (source IN ('inline','frontmatter')),
    PRIMARY KEY (note_id, tag_id, source)
);

CREATE INDEX idx_note_tags_tag  ON note_tags(tag_id);
CREATE INDEX idx_note_tags_note ON note_tags(note_id);
```