# Phase 13 — Bookmarks (sidebar tabs + SQLite library)

**Completed:** 2026-09-27 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

---

## Objective

Implement `ROADMAP.md` Phase 13 in two halves, both listed in `TASKS.md`:

1. **Establish the database.** Create the SQLite library described in
   `database_schemas.md` — `books` (identity by content hash), `book_locations`,
   `notes`, `tags`, `note_tags`, `bookmarks` — with the schema applied exactly once,
   foreign keys enforced on every connection, and the notes root holding Markdown bodies
   for Phase 14.
2. **Add tabs to the side panel.** Turn the Phase 12 notes-only pane into a real
   sidebar: a `QTabWidget` whose tabs are **Bookmarks** and **Notes**, both always
   present, with the tab strip hiding itself when only one tab is visible, and the
   sidebar's state (active tab, width, visibility) persisted through `QSettings`.

`Ctrl+B` had to move with it: the Phase 9 scaffold kept bookmarks as a per-viewer
in-memory dict of PyMuPDF pointers, which is not what the schema describes
("Bookmarks and notes are APP-LOCAL (SQLite)").

---

## Solution

### Storage layer (`app/core/`)

| File | Change |
|---|---|
| `app/core/schema.sql` | **New.** The schema from `database_schemas.md`, with the DDL wrapped in one transaction and `PRAGMA user_version = 1` as the *last* statement. `PRAGMA foreign_keys` was removed from the file: it is per-connection state and cannot live in a once-only script. |
| `app/core/hashing.py` | **New.** `content_hash(path, algorithm)` — sha256/blake2b, streamed in 1 MiB blocks, always lowercase hex. |
| `app/core/database.py` | **New.** `Database` plus `Book`/`Bookmark`/`Note` dataclasses: schema bootstrap, books and locations, notes on disk, bookmarks. No connection is held open. |

**Run once, never twice.** `Database.initialize()` reads `PRAGMA user_version` first: `0`
means a brand-new file (or a run that never finished) so the script is executed, `1` means
the schema is already there and the script must not be re-run, and anything higher raises
`SchemaVersionError` rather than downgrading a newer library. Because the version is the
last statement *inside* the script's transaction, a failure halfway through leaves the
version at 0 and the next launch retries instead of leaving half a schema behind.

**Content-hash identity.** `ensure_book(path, title, author)` hashes the file, finds or
creates the `books` row on `(content_hash, hash_algo)`, and records the path in
`book_locations`. The first path a book is seen at becomes the primary one (`is_primary = 1`
satisfies the partial unique index); a second path for the same bytes is only a hint. A
`(path, mtime_ns, size)` cache means a document is hashed once per open, not once per tab
switch or bookmark toggle.

**Notes as files, metadata in the database.** `create_note` writes
`<notes_root>/<book-hash>/note-<uuid>.md` and stores only the *relative* path, creating the
per-book directory on first use. `update_note_body` rewrites the file and refreshes
`updated_at`/`file_mtime`/`file_size` in application code — there is deliberately no trigger.
`reassign_note_book` moves the file and updates `book_id` + `file_path` together; because
SQLite cannot join a filesystem rename to a row update, the move is undone if the `UPDATE`
fails, so the file and the row can never disagree. `delete_note` and `delete_book` prune a
book directory once it is empty; `delete_book(remove_notes=False)` is the documented
orphaning path.

**Connections.** Every operation opens its own connection and closes it. `connect()` sets
`PRAGMA foreign_keys = ON` on each one — the pragma is per-connection, so putting it in the
schema file (which runs once) would silently disable every `ON DELETE CASCADE`.

### Sidebar (`app/ui/`)

| File | Change |
|---|---|
| `app/ui/bookmarks_panel.py` | **New.** `BookmarksPanel(QWidget)`: a "Contents" `QTreeView` fed by `Document.get_toc()` above a "Bookmarks" `QListWidget` fed by the `bookmarks` table, in one vertical `QSplitter`. Emits `page_requested(int)` and `mark_removed(int)`. |
| `app/ui/sidebar.py` | **New.** `Sidebar(QTabWidget)`: tabs `Bookmarks` and `Notes`, `setDocumentMode(True)`, and `sync_tab_bar_visibility()` which hides the strip when fewer than two tabs are visible. `setTabVisible` is overridden because Qt has no tab-visibility signal to hook. |
| `app/ui/main_window/notes.py` | **Deleted** → `app/ui/main_window/sidebar.py`. `NotesMixin` became `SidebarMixin`: the splitter's left child is now the `Sidebar`, and the layer gained `refresh_sidebar`, `navigate_to_page`, `remove_bookmark`, `save_sidebar_tab`, the `sidebar/` `QSettings` keys, and a `closeEvent` that flushes the layout. |
| `app/ui/main_window/bookmarks.py` | `toggle_bookmark` now writes to SQLite through `book_id_for_viewer(viewer)` instead of the viewer's dict. |
| `app/ui/main_window/commands.py` | `CommandsMixin` now extends `SidebarMixin`; `create_notes_panel_action` became `create_sidebar_action` (label "Side Panel"), keeping `Ctrl+Shift+E` / `F9`. |
| `app/ui/main_window/window.py` | Creates and initializes the `Database` before `create_sidebar()`. |
| `app/ui/main_window/base.py` | Declares `database: Database` next to `session_manager` and `tabs`. |
| `app/ui/main_window/theme.py` | Dark QSS for `QTabWidget#sidebar` (tab strip, pane), `QWidget#bookmarksPanel`, `QLabel#panelHeader`, `QTreeView#outlineView` and `QListWidget#marksList`. |
| `app/ui/viewer_tab.py` | Dropped the in-memory `bookmarks` dict, `toggle_bookmark` and `bookmark_pages` — SQLite is now the single source of truth. |
| `app/core/pdf_engine.py` | Added `title`, `author` (blank metadata normalised to `None` so it cannot overwrite a stored title) and `outline()` for the `(level, title, page)` rows. |

### Why the sidebar inherits the notes layer

The `QSplitter` needs `self.tabs`, which only exists from `DocumentsMixin` (layer 6)
onwards, so the sidebar has to stay above it. That creates one ordering problem: the write
belongs to `BookmarksMixin` (layer 4) but the panel it must refresh is owned by:
`SidebarMixin` (layer 7). The chain already documents that `super()` stays cooperative, so
`SidebarMixin.toggle_bookmark` calls `super().toggle_bookmark()` and then
`refresh_sidebar()` — one operation, split along the layer that owns each half.

### Persistence keys

`QSettings("linux-pdf-reader", "Fallow PDF Reader")`, the same file as Phase 12:
`sidebar/splitter_state`, `sidebar/visible`, `sidebar/width`, `sidebar/tab` (by *name* —
`"bookmarks"` / `"notes"` — so reordering the tabs cannot restore the wrong one).
`read_sidebar_setting` falls back to the old `notes/*` keys so a layout saved by Phase 12
carries over.

`QSettings.value(key, default, bool)` is deliberately not used for the boolean:
Qt converts through `QVariant.toBool`, where every non-empty *string* is true, so a stored
`"false"` comes back as `True`. `setting_bool()` reads untyped and converts explicitly.

The outline stores zero-based pages in `Qt.ItemDataRole.UserRole`; a heading from the table
of contents whose page is `-1` (Alice's PDF ends with "Free eBooks at Planet eBook") stores
`None`, so activating it does nothing instead of jumping to page 1.

---

## Actions Performed

1. Read `AGENTS.md`, `SPEC.md`, `ROADMAP.md`, `TASKS.md`, `database_schemas.md`,
   `reading_guide.md`, repo memory, and the whole `app/` package to place the work in the
   existing mixin chain.
2. Wrote `app/core/schema.sql`, `app/core/hashing.py`, `app/core/database.py`.
3. Ran a throwaway storage script (`/tmp/verify_phase13_db.py`) and fixed the one defect it
   found; re-ran to clean.
4. Wrote `app/ui/bookmarks_panel.py`, `app/ui/sidebar.py`, and the new
   `app/ui/main_window/sidebar.py`; deleted `notes.py`; rewired `bookmarks.py`,
   `commands.py`, `window.py`, `base.py`, `theme.py`, `viewer_tab.py`, `pdf_engine.py`.
5. Ran a throwaway headless UI script (`/tmp/verify_phase13_ui.py`, `QT_QPA_PLATFORM=offscreen`,
   temporary `XDG_CONFIG_HOME`/`XDG_DATA_HOME`) and fixed two real defects it found.
6. Smoke-ran the entrypoint (`.venv/bin/python -m app.main`) under a temporary XDG root and
   confirmed it creates `library.db`, the settings `.conf`, and `session.json`, then keeps
   running until the timeout fires.
7. Rendered `window.grab()` snapshots and verified them by sampling pixels (see below),
   because the downscaled preview of a full-window grab was not trustworthy.

### Defects found and fixed by verification

- **The menu checkmark drifted after the first-run layout.** `apply_default_sidebar_layout`
  shows the pane directly instead of going through `set_sidebar_visible`, so the
  `View > Side Panel` action kept the checkmark it was given before the first resize. Fixed by
  calling `sync_sidebar_action()` from that path too.
- **The tab strip never reacted to a hidden tab.** `setTabVisible` emits no signal, so
  "hide the tab bar when only one tab is open" could not fire. Fixed by overriding
  `setTabVisible` to re-run `sync_tab_bar_visibility()`.
- (Test-side, not code) A `file_size` assertion compared against 12 bytes for a 13-byte
  file, and three layout assertions assumed the offscreen window was wider than it is.

### Snapshot verification, not eyeballing

Grab previews of the full 724×533 window rendered misleadingly light in the review tool, so
the snapshots were checked by sampling pixels and by cropping the sidebar:

```
/tmp/fallow-phase13-sidebar.png   pixel (150,300) = (41,46,57)   #292E39 sidebar pane
                                  pixel (520,260) = (46,52,64)   #2E3440 document background
                                  pixel (8,8)     = (239,239,239) empty (global-menu) menu bar strip
                                  mean luma 64.1
```

The cropped sidebar image showed the expected layout: `[Bookmarks][Notes]` tab strip, a
"Contents" tree with *Alice's Adventures in Wonderland* → Chapter I…XII (plus the
destination-less "Free eBooks at Planet eBook" row), and a "Bookmarks" list reading
"Rabbit hole / Page 9 / Tea party" — the two labelled marks and the unlabelled one, with the
one-based fallback label.

---

## Verification Output

### Storage layer

`PYTHONPATH=/home/redram/python/Fallow .venv/bin/python /tmp/verify_phase13_db.py`
(exit code `0`, 40 checks, all passing):

```
data root: /tmp/fallow-phase13-db-8mbuld0y/linux-pdf-reader
db: .../library.db size=102400
[PASS] all schema tables exist -> ['book_locations', 'bookmarks', 'books', 'note_tags', 'notes', 'tags']
[PASS] user_version is the schema version -> 1
[PASS] foreign_keys ON for a fresh connection -> 1
[PASS] journal mode is WAL -> wal
[PASS] content hash is lowercase hex -> c0d87d2223caaf30f56097ac701e4f9c74fb501a646e16bce1369a383f2bbd26
[PASS] book id cached on the second call -> 1
[PASS] identical bytes resolve to the same book -> (1, 1)
[PASS] two locations, one primary -> [.../alices-adventures-in-wonderland.pdf, .../copy.pdf]
[PASS] marks come back ordered -> [2, 7]
[PASS] negative page rejected -> Page numbers are zero-based and cannot be negative: -1
[PASS] note path is relative to the notes root -> c0d87d22.../note-7da44446-....md
[PASS] updated_at maintained in app code -> ('2026-09-27 18:07:54', '2026-09-27 18:07:54')
[PASS] db file_size refreshed -> 13
[PASS] absolute note path rejected -> Note path must be relative to the notes root: '/etc/passwd'
[PASS] reassigned file moved on disk -> bb111bbb.../note-7da44446-....md
[PASS] old book directory pruned -> c0d87d2223caaf30f56097ac701e4f9c74fb501a646e16bce1369a383f2bbd26
[PASS] body follows the move -> '# First\nbeta\n'
[PASS] re-initialize keeps data -> 2
[PASS] re-initialize keeps the version -> 1
[PASS] deleting a book removes its notes directory -> .../bb111bbb...
[PASS] unsafe directory name rejected -> Refusing to use an unsafe book directory name: '../../etc'
[PASS] newer schema version refused -> SchemaVersionError
[PASS] failed script leaves version at 0 -> 0
all checks passed
```

### Sidebar and window integration

`QT_QPA_PLATFORM=offscreen`, temporary `XDG_CONFIG_HOME`/`XDG_DATA_HOME`,
`PYTHONPATH=/home/redram/python/Fallow .venv/bin/python /tmp/verify_phase13_ui.py`
(exit code `0`, 64 checks, all passing):

```
splitter width: 724 span: 720 sizes: [324, 400]
outline rows from get_toc(): 14
first outline row: (1, 'Alice’s Adventures in Wonderland', 1)
[PASS] sidebar is a tab widget -> Sidebar
[PASS] tabs are Bookmarks and Notes -> ['Bookmarks', 'Notes']
[PASS] both tabs are always present -> [True, True]
[PASS] tab bar hidden when one tab is left -> False
[PASS] tab bar returns with the second tab -> True
[PASS] sidebar tab restores by name -> notes
[PASS] outline stores zero-based pages -> (0, 1)
[PASS] activating the outline moves the viewer -> (0, 0)
[PASS] book hash is the file's sha256 -> c0d87d2223caaf30...bbd26
[PASS] Ctrl+B adds a mark to the panel -> 1
[PASS] mark is persisted for the book -> [4]
[PASS] toggling again removes the mark -> []
[PASS] panel can remove a mark -> 0
[PASS] second document shows no marks -> 0
[PASS] renamed copy keeps the same book (and marks) -> [1]
[PASS] document pane keeps its 400px floor -> [324, 400]
[PASS] palette exposes Side Panel exactly once -> 1
[PASS] palette row shows both keys -> Ctrl+Shift+E, F9
[PASS] no shortcut collision -> []
[PASS] active tab stored -> notes
[PASS] active tab survives a restart -> notes
[PASS] width survives a restart -> 360
[PASS] marks are still there after a restart -> 1
[PASS] hidden state survives a restart -> False
[PASS] action is unchecked after restoring a hidden sidebar -> False
[PASS] deleting the DB rebuilds it -> .../library.db
[PASS] rebuilt DB is empty of marks -> 0
all checks passed
```

### Entrypoint

```
XDG_DATA_HOME=.../data XDG_CONFIG_HOME=.../config QT_QPA_PLATFORM=offscreen \
  timeout 8 .venv/bin/python -m app.main
exit=124 (124 = still running when the timeout fired)
XDG/config/linux-pdf-reader/Fallow PDF Reader.conf
XDG/config/linux-pdf-reader/session.json
XDG/data/linux-pdf-reader/library.db
```

Notes on the runs:

- The offscreen window is 724px wide (its own minimum: 320 sidebar + 400 document + handle),
  so the first run exercises the narrow-window rule (auto-collapse below 900px). The 30%
  rule and both clamps are covered by `default_sidebar_width()` directly, and the layout
  invariants (document pane never below 400, sidebar never below 320, panes filling the
  span) are asserted against the real splitter.
- `setTabVisible`, `remove_current_mark` and `navigate_to_page` are called directly rather
  than through a synthesized key press: `QTest.keyClick(widget, key)` bypasses the
  shortcut map, so it would prove nothing about the widget-scoped `Delete` shortcut.

---

## References Used

1. `sqlite3` — connection context managers, `executescript`, `PRAGMA user_version`,
   `lastrowid`, `ON CONFLICT DO UPDATE`:
   <https://docs.python.org/3/library/sqlite3.html>
2. SQLite `PRAGMA foreign_keys` (per-connection, off by default) and `user_version`:
   <https://www.sqlite.org/pragma.html#pragma_foreign_keys>
3. `QTabWidget` — `setDocumentMode`, `setTabVisible`/`isTabVisible`, `currentChanged`, and
   tab-bar styling:
   <https://doc.qt.io/qt-6/qtabwidget.html>

---

## Optional steps

- Add `Ctrl+Shift+B` (or a second command-palette entry) that opens the sidebar *on the
  Bookmarks tab*, so the marks list is one keystroke away instead of two.
- Persist the `BookmarksPanel` splitter position too, so a reader who enlarges the marks list
  keeps it between sessions.
- Rename or label a mark from the panel (`Database.add_bookmark` already accepts and updates
  a label) and seed the default label from the page's first text line
  (`Page.get_text().strip().splitlines()[0]`).
- Add a `tags`/`note_tags` accessor set (`ensure_tag`, `link_tag`, `tags_for_note`) when
  Phase 14 starts parsing `#inline` and front-matter tags — the tables are already there and
  the `source` column is the reason re-parsing can clean up only the tags it owns.
- Hash in a background `QThread`: a 1 MiB-block SHA-256 of a large PDF is quick, but it is
  still synchronous work on the UI thread during the first `refresh_sidebar` for a document.
- Add `PRAGMA user_version` migration steps for version 2 (the file's own header says "add a
  migration in app code"), rather than the current behaviour of refusing a newer library.

## Possible problems

- **A first run on a screen narrower than 900px leaves the sidebar hidden.** That is the
  Phase 12 rule and it is intentional, but the sidebar is now the only way to reach both the
  outline and the marks, so a small-screen user has to toggle `F9` once before the DB work
  pays off. A "remember the first toggle" default would fix it.
- **The library is per-machine and not portable.** Bookmarks are app-local rows in
  `library.db`; the PDFs themselves carry nothing. Copying a PDF to another machine starts a
  fresh library, which the schema documents but a user will not expect.
- **Two copies of a PDF are one book by design.** Marking page 5 in one copy marks it in the
  other, and deleting a book removes the notes of both. The schema calls this the point of
  content-hash identity; it will still read as a bug to anyone who has not read
  `database_schemas.md`.
- **`Database.initialize()` failures are fatal.** An unwritable `$XDG_DATA_HOME` raises out of
  `MainWindow.__init__` and the application does not start at all, rather than running with
  bookmarking disabled. A degraded mode would need every `self.database` use to be
  Optional-guarded.
- **Bookmarks are not marked in the rendered page.** The pane lists them, but the page canvas
  gets no marker, so a reader who bookmarks a page and then scrolls away has to consult the
  sidebar to find it again. (This replaced the Phase 9 PyMuPDF pointer scaffold, which is why
  `RenderEngine.make_bookmark` is now unused.)
- **`refresh_sidebar` re-reads on every document-tab change.** The query is tiny and the hash
  is cached, but the outline tree is rebuilt from scratch each time; a per-book outline cache
  would remove the flicker on fast tab switching.
- **A note whose file was deleted outside the app** still has its row. `read_note_body`
  returns `None` rather than raising, and `reassign_note_book` tolerates the missing file, but
  nothing reconciles `file_mtime`/`file_size` against disk yet — that is Phase 14's external
  edit detection.
- **The sidebar is a child of the window, not a `QDockWidget`.** Phase 13's sketch mentioned
  `Qt.LeftDockWidgetArea`; the splitter was kept because Phase 12 already built the layout
  rules (30% default, drag auto-hide, `QSettings` state) around it. A dock would mean
  re-deriving all of that, and would float the pane out of the maximized window.

---

# Phase 13, follow-up: `missing` and `troubleshooting`

**Added:** 2026-09-27 · Same log, same phase: the reader extended `TASKS.md` with a `missing`
list and a `troubleshooting` list after the first pass was signed off.

---

## Objective

Close the two new lists in `TASKS.md`:

1. **missing** — reach the sidebar from the command palette (a `bookmarks` entry that reveals and
   focuses that tab, and a `notes` entry that does the same *and* creates a note to type in), and
   give the notes pane a "+" button.
2. **troubleshooting** — survive a non-writable `XDG_DATA_HOME` instead of crashing, keep the app
   usable without persistence, say so non-blockingly, offer a settings dialog for a writable
   location, and stop re-reading and rebuilding the outline on every refresh.

Exporting bookmarks and notes was explicitly deferred by the reader to a later phase.

---

## Solution

| File | Change |
|---|---|
| `app/core/database.py` | **New** `StorageError` (with `SchemaVersionError` now under it), `TEMPORARY_MODE_MESSAGE`, `derive_note_title()`, and `open_library()`. `Database` gained `temporary` + `temporary_reason`; `initialize()` wraps `OSError`/`sqlite3.Error` as `StorageError`; `update_note_body` now also stores the title. |
| `app/ui/notes_panel.py` | Rewritten from placeholder to the real pane: header with a "+" `QToolButton`, a note `QListWidget`, and a `QPlainTextEdit` in a vertical `QSplitter`. Debounced (700 ms) autosave, flushed on note change and close. |
| `app/ui/library_dialog.py` | **New.** `LibraryLocationDialog`: shows the active/selected folder, warns when the session is temporary, "Choose Folder…" / "Use Default Location" / OK / Cancel, and the same per-dialog theming the palette uses. |
| `app/ui/main_window/base.py` | `create_settings()`, `create_storage()`, `set_storage_notice()`, `switch_library()`, `configured_data_root()`, plus `setting_bool`/`setting_int` moved here from the sidebar layer (they are no longer sidebar-specific). |
| `app/ui/main_window/sidebar.py` | `_outline_cache` as `dict[book_id, rows]` + `outline_for_book()`, `show_sidebar_tab()`, `create_note()`, `reload_notes()`, `open_note()`, `save_note()`, a `switch_library` override that clears the cache, and a `closeEvent` that flushes the editor. |
| `app/ui/main_window/commands.py` | `File > Library Location…`, `Edit > New Note`, `View > Show Bookmarks`, and `show_library_dialog()`. |
| `app/ui/main_window/window.py` | `create_settings()` then `create_storage()`, replacing the inline `Database()` construction. |
| `app/ui/bookmarks_panel.py`, `app/ui/sidebar.py`, `app/ui/main_window/theme.py` | Skip-the-rebuild guards and `focus_default_view()`; `BOOKMARKS_TAB`/`NOTES_TAB` constants and `focus_active_panel()`; dark QSS for the notes list, editor, "+" button, and the status-bar notice. |

### Degrading instead of aborting

`Database.initialize()` still fails loudly, but it raises `StorageError` rather than letting an
`OSError` escape, and `open_library()` is the only thing the window calls:

```
try:    Database(preferred).initialize()          -> (database, None)
except StorageError:
        Database(tempfile.mkdtemp(), temporary=True).initialize()
                                                   -> (database, TEMPORARY_MODE_MESSAGE)
```

The reader keeps every feature — bookmarks, notes, outline — against the throwaway store; only
the data is forgotten at exit, which is what "works without persistence" means here. The wording
of the banner is exactly the sentence `TASKS.md` asked for, and the reason
(`Cannot use the library at /path: [Errno 17] File exists`) is kept on
`Database.temporary_reason` for the tooltip, because a sentence in a status bar has no room for it.

### A notice that survives other status messages

`QStatusBar.showMessage(text, 0)` looks permanent but is not: the next transient message
("Zoom 115%", "Bookmark added") replaces it and then clears, taking the warning with it. The
notice is therefore a `QLabel` added with `addPermanentWidget`, bold via `QFont` so it stands out
in both themes, with the colour coming from the dark stylesheet only (`QLabel#storageNotice`,
Nord yellow `#EBCB8B`) so the light theme keeps its default text colour.

### Three cache layers, each doing one job

* `SidebarMixin._outline_cache: dict[int, list[OutlineEntry]]` — avoids asking PyMuPDF for a
  document's table of contents more than once per book per session.
* `BookmarksPanel.set_outline()` / `set_marks()` and `NotesPanel.set_notes()` — compare the rows
  they were given with the rows they already show and return early, so a refresh cannot drop the
  reader's selection or the tree's expansion state.
* `Database._book_id_cache` — from the first pass, so hashing happens once per file.

The first attempt at the outline cache held only the *active* document, which still re-read the
PDF when moving back to an earlier tab; the verification script caught that (2 expected, 3
observed) and the cache became a dict. `switch_library()` clears it, because book ids belong to
one database and a stale entry would describe the wrong book.

### Note titles follow the body

The notes list has to name a row before anyone clicks it, and reading every file to do that would
be a filesystem walk per refresh. `Database.update_note_body` therefore derives `notes.title` from
the body's first non-empty line (dropping a leading `#`), and `NotesPanel.update_note` re-labels
the row in place. An untyped new note shows "Page 12" from the page it was created on.

---

## Actions Performed

1. Extended `app/core/database.py` (error hierarchy, temporary mode, `open_library`,
   title derivation) and re-ran the first-pass storage script.
2. Rewrote `app/ui/notes_panel.py` and edited `bookmarks_panel.py`, `sidebar.py`,
   `base.py`, `main_window/sidebar.py`, `commands.py`, `window.py`, `theme.py`.
3. Wrote `app/ui/library_dialog.py`.
4. Ran a new throwaway script (`/tmp/verify_phase13_followup.py`, offscreen, temporary
   `XDG_CONFIG_HOME`/`XDG_DATA_HOME`, `storage/data_root` pointed at a *file* so the folder cannot
   be created) and fixed the two defects it found.
5. Re-ran both first-pass scripts to confirm no regression (192 checks green in total) and
   smoke-ran `.venv/bin/python -m app.main`, which created `library.db`, the settings `.conf`,
   `session.json`, and the `notes/` directory, then kept running.
6. Rendered a snapshot of the notes tab and the status-bar notice and inspected the crop.

### Defects found and fixed by verification

- **The outline cache only held one document.** `refresh_sidebar` re-read the PDF when the reader
  returned to an earlier tab (expected 1 call, got 3 overall). Changed to a per-book dict, which
  is also what "cache the outline data" asks for with several documents open.
- **The status-bar notice could be lost.** An early draft used `showMessage(text, 0)`; the test
  harness could not even see it, because that form is cleared by the next transient message.
  Replaced with a permanent widget.

### Snapshot

Cropping the sidebar (`QImage.copy`) rather than previewing the whole window — a full-window grab
rendered misleadingly light in review, as in the first pass:

```
temporary: True
notes list: ['Chapter III', 'Second note, still untitled']
editor holds: 'Second note, still untitled\n'
note titles in db: ['Chapter III', 'Second note, still untitled']
```

The crop showed `[Bookmarks][Notes]` with **Notes** selected, the "Notes" header with its "+"
button, the two titles (the first derived from `# Chapter III`), the editor holding the second
note, and the status bar reading `New note for page 12` beside the yellow `⚠ Notes and bookmarks
cannot be saved in this environment. Running in temporary mode.`

---

## Verification Output

`QT_QPA_PLATFORM=offscreen`, temporary `XDG_CONFIG_HOME`/`XDG_DATA_HOME`,
`PYTHONPATH=/home/redram/python/Fallow .venv/bin/python /tmp/verify_phase13_followup.py`
(exit code `0`, 88 checks, all passing):

```
[PASS] it falls back to temporary mode -> True
[PASS] the notice is the agreed wording -> 'Notes and bookmarks cannot be saved in this environment. Running in temporary mode.'
reason: Cannot use the library at /tmp/fallow-followup-3pl4pkbv/blocked: [Errno 17] File exists: '.../blocked'
[PASS] bookmarks work in temporary mode -> [3]
[PASS] notes work in temporary mode -> '# Temporary\n'
[PASS] a writable root reports no notice -> None
[PASS] the window uses a temporary library -> /tmp/fallow-library-txxk9pgu
[PASS] the notice is permanent, not a transient message -> QStatusBar
[PASS] the notice explains the fix -> ...File ▸ Library Location… lets you choose a folder that can be written.
[PASS] the plus button creates a note -> 1
[PASS] the created note is on the current page -> 7
[PASS] the editor is now editable -> False
[PASS] the editor is focused -> QPlainTextEdit
[PASS] typing arms the autosave timer -> 700
[PASS] nothing is written before the debounce fires -> ''
[PASS] the title is derived from the body -> Chapter two
[PASS] an unsaved edit is pending -> True
[PASS] switching documents saves the pending edit -> '# Chapter two\nrabbit hole\ncuriouser\n'
[PASS] the editor is emptied for a document with no notes -> None
[PASS] clicking a row opens that note -> (1, 1)
[PASS] the palette offers Show Bookmarks -> 
[PASS] the palette offers New Note -> 
[PASS] palette titles stay unique -> []
[PASS] no new shortcut collision -> []
[PASS] Show Bookmarks focuses the marks list -> QListWidget
[PASS] New Note reveals the sidebar on the notes tab -> (True, 'notes')
[PASS] New Note focuses the editor -> QPlainTextEdit
[PASS] a cold cache reads the outline once -> 1
[PASS] a second refresh reuses the cache -> 1
[PASS] a different document is read once -> 2
[PASS] returning to the first document reuses its cache -> 2
[PASS] an unchanged outline is not rebuilt -> (True, True)
[PASS] an unchanged marks list keeps its selection -> 0
[PASS] switching opens the chosen folder -> /tmp/fallow-followup-otm6d8eh/chosen
[PASS] the notice is cleared -> 
[PASS] switching to an unusable folder degrades again -> /tmp/fallow-library-3am6q72c
[PASS] the notice comes back -> ⚠ Notes and bookmarks cannot be saved in this environment. Running in temporary mode.
[PASS] the default location can be restored -> None
[PASS] the dialog warns about temporary mode -> Notes and bookmarks could not be saved in the configured loc
[PASS] the pending edit is not on disk yet -> ''
[PASS] closing flushes the pending edit -> 'typed just before quitting'
all checks passed
```

Full palette after the change — 17 entries, every title unique, no duplicate key sequences:

```
['Bookmark Page', 'Close Tab', 'Dark Mode', 'Find', 'Go to Page', 'Library Location…', 'New Note',
 'Next Page', 'Open', 'Previous Page', 'Quit', 'Reset Zoom', 'Show Bookmarks', 'Side Panel',
 'Tab Search', 'Zoom In', 'Zoom Out']
```

Regression runs on the first pass (both exit `0`, no failures): storage 40 checks, sidebar/window
64 checks. Entrypoint smoke test still exit `124` (running when the timeout fired) with
`library.db`, `Fallow PDF Reader.conf`, `session.json`, and `notes/` created.

Notes on the run:

- A *file* stands in for the unwritable folder (`Path.mkdir` raises `FileExistsError` even with
  `exist_ok=True`), because chmod-based tests pass when the suite runs as root.
- The autosave debounce is asserted as a state machine (timer armed → nothing on disk → flush →
  body and title written) rather than by sleeping, so the check is instant and deterministic.
- The outline call counter patches `RenderEngine.outline` on the *class*; patching one engine
  instance only counted that document and made the cross-document assertions meaningless.

---

## References Used

1. `tempfile.mkdtemp` — throwaway directories for the temporary library:
   <https://docs.python.org/3/library/tempfile.html#tempfile.mkdtemp>
2. `QPlainTextEdit` and `QTimer` (single-shot debounce) for the autosaving editor:
   <https://doc.qt.io/qt-6/qplaintextedit.html>
3. `QStatusBar` — `showMessage` versus `addPermanentWidget`, and why a permanent notice is not a
   transient message:
   <https://doc.qt.io/qt-6/qstatusbar.html>

---

## Optional steps

- Make the `storageNotice` label clickable so it opens the library dialog directly, instead of
  telling the reader to find `File ▸ Library Location…` in the tooltip.
- Offer to *move* or *copy* an existing library to the newly chosen folder, and detect when the
  chosen folder already holds a library so the dialog can say what it found.
- Remember a "don't warn again" acknowledgement for the temporary banner, for readers who are
  deliberately running read-only.
- Give `Show Bookmarks` and `New Note` shortcuts once they can be chosen without colliding
  (`Ctrl+Shift+B` is free) — the palette currently shows them with no key.
- Add a plain `Show Notes` entry: the reader asked for the notes entry to create a note, so this
  pass has one action that does both, and reveal-without-creating has no entry yet.
- Persist the `NotesPanel` splitter position (list vs editor) the way the sidebar's is persisted.

## Possible problems

- **A temporary library is invisible in the window title.** The warning lives in the status bar;
  a reader with a maximized window and no habit of looking there can type a long note and lose it
  at exit. Closing with unsaved bindings would be the honest fix.
- **The temporary fallback never retries.** If the data directory becomes writable while the app
  is running, the session stays on the throwaway store until it is restarted.
- **A corrupt `library.db` degrades too.** Any `sqlite3.Error` during `initialize()` becomes a
  temporary session, so a damaged library silently looks like an unwritable folder and the real
  error only survives in the tooltip.
- **The library choice is stored even when it fails.** That is deliberate (it is a preference),
  but it means a typo in a path keeps producing the banner on every launch until the dialog is
  used again.
- **Switching libraries quietly changes what the reader sees.** The current folder's notes and
  marks stay on disk but disappear from the UI, and the notes list/editor empty out. The dialog
  says nothing is copied; there is no way back other than choosing the old folder again.
- **Note titles are derived, never chosen.** Editing the first line renames the note, and a note
  whose body starts with a long line gets a long label that the narrow sidebar elides.
- **Autosave is debounced but not transactional with the editor.** A save writes the whole body;
  a crash between the file write and the row update leaves `title`/`file_size` stale, and nothing
  reconciles them yet (Phase 14's external-edit detection).
- **`_outline_cache` grows one list per book per session.** Small in practice (a few hundred
  tuples for a long book), but it is never pruned.
- **`switch_library()` does not re-open the documents.** The open tabs keep their viewers and
  their `current_page`; only the sidebar is repointed. Nothing caches per-document data from the
  old library today, so this is safe for now, but any future per-document cache must be cleared
  in the same place as `_outline_cache`.

---

# Phase 13, follow-up 2: `Show Notes`, and Markdown feedback

**Added:** 2026-09-27

---

## Objective

Two small pieces of feedback after reading the follow-up back:

1. Add the reveal-only `Show Notes` palette entry, so the notes pane can be opened without
   creating a note in it.
2. Record, in `useful_features.md`, that rendering Markdown inside the app belongs to a later
   phase — and provide the considerations that phase should weigh, since the reader wanted that
   feedback written down where the feature is noted rather than only discussed.

The editor stays a plain-text `QPlainTextEdit` over Markdown files on disk; that was already the
case and this change does not alter it.

---

## Solution

| File | Change |
|---|---|
| `app/ui/main_window/commands.py` | Imports `NOTES_TAB` alongside `BOOKMARKS_TAB` and adds `View > Show Notes`, wired with `partial(self.show_sidebar_tab, NOTES_TAB)`. No shortcut, so the palette can enumerate it and nothing new can collide. |
| `useful_features.md` | New `### render markdown in the app` under `## Notes`: the goal, where the code already stands, and nine considerations for the phase that picks it up. `### presentation` now points at it. |
| `TASKS.md` | The `notes` palette entry is described as satisfied by two actions instead of one, and the Phase 14 carry-over paragraph points at the new feedback section. |

`Show Bookmarks` and `Show Notes` are now the same shape — one `partial` binding each onto
`show_sidebar_tab` — while `New Note` stays the one entry that creates something. That split is
the point: an entry that both reveals a pane and writes to the library is surprising when the
reader only wanted to look.

### The feedback written into `useful_features.md`

The nine points are grounded in this codebase rather than generic Qt advice:

- the Markdown file is the source of truth, and `QTextDocument.toMarkdown()` normalises
  whitespace and list markers, so a round-trip must never be written back to disk;
- `QSyntaxHighlighter` on the existing `QPlainTextEdit` is what "minimal highlighting" actually
  needs — no widget swap, so editing, the 700 ms autosave, the cursor and the scroll position are
  untouched;
- true rendering (`setMarkdown`) belongs behind an edit ⇄ preview toggle, because a
  `QTextBrowser` is read-only in practice;
- live re-rendering must be debounced like the save, or it fights the typist;
- a `QTextDocument` brings its own palette, which is the same dark-mode trap the sidebar and the
  command palette already had to handle;
- the sidebar is 320–640px wide, so a rendered note is better served by the note-placement-icon
  dialog the file already lists;
- tag parsing and rendering must share one parser in `app/core/markdown.py`, or fenced code will
  produce phantom headings and tags;
- export is an action, not a format, because the notes already are Markdown files;
- `highlightBlock` is per block, so keep the patterns per block.

---

## Actions Performed

1. Added the action and its import in `app/ui/main_window/commands.py`.
2. Wrote the `render markdown in the app` section into `useful_features.md` and cross-linked it
   from `### presentation`.
3. Updated the two affected `TASKS.md` paragraphs.
4. Extended `/tmp/verify_phase13_followup.py` with four checks for the new entry (presence, reveal,
   tab selection, focus) plus one that it does *not* create a note, and re-ran all three scripts.

---

## Verification Output

```
verify_phase13_db          exit=0 pass=40 fail=0
verify_phase13_ui          exit=0 pass=64 fail=0
verify_phase13_followup    exit=0 pass=93 fail=0
no failures
```

Palette after the change — 18 entries, all titles unique, no duplicate key sequences:

```
['Bookmark Page', 'Close Tab', 'Dark Mode', 'Find', 'Go to Page', 'Library Location…', 'New Note',
 'Next Page', 'Open', 'Previous Page', 'Quit', 'Reset Zoom', 'Show Bookmarks', 'Show Notes',
 'Side Panel', 'Tab Search', 'Zoom In', 'Zoom Out']
```

```
[PASS] the palette offers Show Notes ->
[PASS] Show Notes reveals the sidebar -> True
[PASS] Show Notes selects that tab -> notes
[PASS] Show Notes focuses the editor -> QPlainTextEdit
[PASS] Show Notes does not create a note -> (3, 3)
```

---

## References Used

1. `QTextDocument.setMarkdown` / `toMarkdown` — the conversion a preview would use, and why a
   round-trip is lossy:
   <https://doc.qt.io/qt-6/qtextdocument.html#setMarkdown>
2. `QSyntaxHighlighter` — `highlightBlock` and per-block highlighting on a `QPlainTextEdit`:
   <https://doc.qt.io/qt-6/qsyntaxhighlighter.html>
3. `QDesktopServices.openUrl` — opening the notes folder for export:
   <https://doc.qt.io/qt-6/qdesktopservices.html#openUrl>

---

## Optional steps

- Give `Show Notes` and `Show Bookmarks` the same shortcut treatment as the side-panel toggle once
  a free pair of keys is chosen, so the pane is reachable without the palette.
- Move the Markdown feedback into the Phase 14 `TASKS.md` list when that phase is opened, so it is
  read at planning time rather than sitting in a wish list.

## Possible problems

- **The palette is now 18 entries and still flat.** Every entry carries its own key label, but with
  three sidebar-related rows (`Side Panel`, `Show Bookmarks`, `Show Notes`) the redundancy is
  starting to show; a `Side Panel ▸` submenu would not survive the palette's flat list, so the
  titles have to stay self-explanatory.
- **`Show Notes` focuses the editor when a note is open and the list when it is not** — correct,
  but it means the same command lands the keyboard in two different places depending on state.
- **The feedback in `useful_features.md` is advice, not a plan.** It will go stale if the editor
  changes first; the file is not covered by any check, unlike the code.
- **`New Note` and `Show Notes` are one keystroke apart in the palette list** and read similarly in
  a fuzzy search (`note` matches both), so a hurried reader can create an empty note while meaning
  to look at the pane.

