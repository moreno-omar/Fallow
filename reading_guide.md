## Meta
- a guide that provides important facts on how to read/review code

### important
- Never re-run schema.sql on an existing DB.
  `Database.initialize()` guards on `PRAGMA user_version`: 0 → run `schema.sql`, 1 → skip.
- `Database.initialize()` raises `StorageError` and must never abort the launch:
  `open_library()` catches it, falls back to a temp dir, and returns the banner text.
  `window.database.temporary` says which one is in use.
- `WindowBase.create_settings()` → `create_storage()` → `create_sidebar()`, in that order:
  the sidebar reads `self.settings` and `self.database`.
- `notes.file_path` is always relative to the notes root.
- `PRAGMA foreign_keys = ON` is per-connection state; `Database.connect()` sets it every time.


### layout

```text
class MainWindow(CommandsMixin)  # → SidebarMixin → DocumentsMixin
                                 # → NavigationMixin → BookmarksMixin
                                 # → FindMixin → ThemeMixin
                                 # → WindowBase(QMainWindow)
```

### structure after refactoring

```text
app/main.py                    entrypoint: QApplication, window, event loop
app/core/
├── database.py   Database         SQLite: books, locations, bookmarks, notes
├── hashing.py    content_hash     book identity (sha256 / blake2b, lowercase hex)
├── pdf_engine.py RenderEngine     PyMuPDF: render, search, outline, metadata
├── schema.sql                     applied once, guarded by PRAGMA user_version
└── session.py    SessionManager   session.json in the XDG config dir
app/ui/
├── bookmarks_panel.py BookmarksPanel  outline tree + marks list
├── library_dialog.py  LibraryLocationDialog  pick the library folder
├── notes_panel.py     NotesPanel      note list, "+" button, autosaving editor
├── sidebar.py         Sidebar         QTabWidget: [Bookmarks][Notes]
└── main_window/
    ├── __init__.py                re-exports MainWindow
    ├── base.py        WindowBase      shared state, session save, close/quit
    ├── theme.py       ThemeMixin      dark-mode stylesheet + re-theming viewers
    ├── find.py        FindMixin       find bar, find_next, the Esc QShortcut
    ├── bookmarks.py   BookmarksMixin  toggle_bookmark (writes to SQLite)
    ├── navigation.py  NavigationMixin page bar, current_viewer, page turn, zoom
    ├── documents.py   DocumentsMixin  open/close/add tabs, Tab Search
    ├── sidebar.py     SidebarMixin    sidebar tabs + splitter, contents, toggle
    ├── commands.py    CommandsMixin   menu bar, shortcut actions, command palette
    └── window.py      MainWindow      __init__ wiring only
```

### side panel / sidebar
- both panels, `notes` and `bookmarks` are always present. Only visible when user decides to pick it.
- `Sidebar` is a `QTabWidget`; its tab bar hides itself when only one tab is visible.
- `SidebarMixin.refresh_sidebar()` is the only thing that fills the panes; it runs on
  document-tab change and after a bookmark toggle.
- bookmark writes live one layer down (`BookmarksMixin.toggle_bookmark`) and the refresh is
  added by `SidebarMixin.toggle_bookmark` through a cooperative `super()` call.
- `NotesPanel` owns no data either: it reports `note_requested` / `note_created` / `note_edited`
  and `SidebarMixin` creates, loads, and saves through `Database`. Autosave is debounced
  (700 ms) and flushed whenever the editor's note changes and from `closeEvent`.
- A note's title is derived from the first line of its body inside `Database.update_note_body`.
- `SidebarMixin._outline_cache` is `dict[book_id, list[OutlineEntry]]`; `outline_for_book()` fills
  it and `switch_library()` clears it (book ids belong to one database).
- The panels themselves skip a rebuild when the rows they are given are unchanged, so a refresh
  keeps the reader's selection and expansion state.

#### persistence
- QSettings → UI state (tab, width, visibility) under `sidebar/*`, and the chosen library folder
  under `storage/data_root`
- SQLite    → bookmarks, notes, tags (keyed by content hash)
  - db:    `$XDG_DATA_HOME/linux-pdf-reader/library.db`
  - notes: `$XDG_DATA_HOME/linux-pdf-reader/notes/<book-hash>/note-<uuid>.md`
  - a library that cannot be written is replaced by a throwaway one under the system temp dir,
    reported by the `storageNotice` label in the status bar