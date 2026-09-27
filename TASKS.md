# TASKS.md - Phase 13 : Bookmarks

- [x] Run `schema.sql` **once** on first creation. Check `PRAGMA user_version` before running.
- [x] Never re-run `schema.sql` on an existing DB.
- [x] Store `content_hash` as lowercase hex.
- [x] `file_path` is **relative to notes root**; never absolute.
- [x] Create/remove `<notes_root>/<book-hash>/` directory when the first note for a book is created.
- [x] On `book_id` reassignment: move the file **and** update `file_path` in one transaction.
- [x] Maintain `notes.updated_at` in app code on every write (no trigger).
- [x] On deleting a book: also remove its `<notes_root>/<book-hash>/` directory, or explicitly document orphaning.
      `Database.delete_book(book_id, remove_notes=False)` is the documented orphaning path.
- [x] Use `PRAGMA foreign_keys = ON` on every connection (it's per-connection, not persistent).
- [x] Two identical PDFs intentionally share notes — don't add per-path disambiguation.
- [x] Create sidebar object
- [x] Persist bookmarks/notes content keyed by document SHA-256 hash
- [x] Persist sidebar state (active tab, width, visibility) via QSettings
- [x] Have `Bookmarks` and `notes` show on it as tabs.
- [x] `Bookmarks` and `notes` always present on sidebar. 
- [x] If only 1 is opened : auto-hide the tab bar
- [x] ~~save as JSON store keyed by the document's file path or SHA-256 hash.~~ Superseded:
      `database_schemas.md` defines bookmarks and notes as **app-local SQLite**
      ("Bookmarks and notes are APP-LOCAL (SQLite)") and `reading_guide.md` agrees
      ("SQLite → bookmarks, notes, tags (keyed by content hash)"). Marks are stored in
      `library.db` keyed by the SHA-256 content hash instead of a JSON file.

## Carried into Phase 14 (Markdown notes)

- [ ] Notes can be created, listed and edited, but only as plain text: Markdown *rendering*,
      a preview pane, and front-matter/inline tag parsing are still to come. The editor is plain
      text and the file on disk is Markdown, so this is a view concern only — see the feedback
      under `render markdown in the app` in `useful_features.md` before planning it.
- [ ] Tag tables (`tags`, `note_tags`) exist in the schema with no accessors.
- [ ] A note's `title` is derived from the first line of its body; there is no rename or reorder.
- [ ] External edits are not detected: `file_mtime`/`file_size` are written on save but never
      compared against what is on disk.

## missing
- [x] `bookmarks` entry should show up in command palette. Displays and make `bookmarks` tab the focus.
      `View > Show Bookmarks` (no shortcut): reveals the sidebar, selects the tab, focuses the marks list.
- [x] `notes` should have a plus sign to create a note
      `NotesPanel.add_button`: creates the note at the viewer's current page, opens it, and focuses the editor.
- [x] `notes` entry in command palette. Displays and makes `notes` tab the focus. Creates new note to type in.
      `Edit > New Note` (no shortcut). Because creating a note is part of that action, the reveal-only
      case got its own entry rather than a second meaning: `View > Show Notes` just shows the tab and
      focuses the pane.



## troubleshooting
- [x] Non-Writable XDG_DATA_HOME -> try to open, degrade gracefully.
      `Database.initialize()` raises `StorageError`; `app.core.database.open_library()` catches it and
      falls back to `tempfile.mkdtemp("fallow-library-")` so the launch never aborts.
- [x] App should work without persistence
      The temporary library is a full store, so every feature keeps working; only the data is forgotten
      at exit. Verified: bookmarks and notes can be created in temporary mode.
- [x] Show a non-blocking banner or status-bar message: "Notes and bookmarks cannot be saved in this environment. Running in temporary mode."
      `WindowBase.create_storage()` adds a permanent bold status-bar `QLabel#storageNotice` (`addPermanentWidget`,
      not `showMessage`, which a later transient message would clear) with the agreed sentence and a tooltip
      naming the reason and the fix.
- [x] Give the user a way to manually specify a writable location via a settings dialog
      `File > Library Location…` opens `app/ui/library_dialog.py`; the choice is stored as
      `storage/data_root` in QSettings and applied by `WindowBase.switch_library()` immediately.
- [x] Cache the outline data (not the widget). Cache the data — a plain Python list of outline entries — and rebuild the widget cheaply from it.
      `SidebarMixin._outline_cache: dict[book_id, list[OutlineEntry]]`, filled by `outline_for_book()`.
      The list is dropped and refilled on `switch_library()`, because book ids belong to one database.
- [x] skip the rebuild entirely if the outline is unchanged
      `BookmarksPanel.set_outline()` (and `set_marks()`, plus `NotesPanel.set_notes()`) compare against the
      rows they already show and return early, which also keeps the reader's selection and expansion state.
