# Fallow — Implementation Log Index

Implementation notes for Fallow, one file per phase, all under `logs/`.
This file is the index; the detail lives in the linked files.

| Phase | Completed | Log |
|---|---|---|
| 1 — Create Window | 2026-09-10 | [`26-09-10_phase1-create-window.md`](logs/26-09-10_phase1-create-window.md) |
| 2 — Render PDF in PySide6 Window | 2026-09-10 | [`26-09-10_phase2-render-pdf.md`](logs/26-09-10_phase2-render-pdf.md) |
| 3 — Open Multiple PDF in Tabs | 2026-09-10 | [`26-09-10_phase3-multiple-pdf-tabs.md`](logs/26-09-10_phase3-multiple-pdf-tabs.md) |
| 4 — Save Session | 2026-09-10 | [`26-09-10_phase4-save-session.md`](logs/26-09-10_phase4-save-session.md) |
| 5 — Preferred PDF Settings | 2026-09-10 | [`26-09-10_phase5-preferred-pdf-settings.md`](logs/26-09-10_phase5-preferred-pdf-settings.md) |
| 6 — Dialog to Pick PDF File | 2026-09-10 | [`26-09-10_phase6-open-file-dialog.md`](logs/26-09-10_phase6-open-file-dialog.md) |
| 7 — Useful Bottom Bar | 2026-09-10 | [`26-09-10_phase7-bottom-bar.md`](logs/26-09-10_phase7-bottom-bar.md) |
| 8 — Dark Mode | 2026-09-10 | [`26-09-10_phase8-dark-mode.md`](logs/26-09-10_phase8-dark-mode.md) |
| 9 — Useful Keyboard Shortcuts | 2026-09-24 | [`26-09-24_phase9-keyboard-shortcuts.md`](logs/26-09-24_phase9-keyboard-shortcuts.md) |
| 10 — Create Command Palette | 2026-09-24 | [`26-09-24_phase10-command-palette.md`](logs/26-09-24_phase10-command-palette.md) |
| 11 — Tabs | 2026-09-24 | [`26-09-24_phase11-tabs.md`](logs/26-09-24_phase11-tabs.md) |
| 12 — Create Panel to View Notes | 2026-09-26 | [`26-09-26_phase12-notes-panel.md`](logs/26-09-26_phase12-notes-panel.md) |
| 13 — Bookmarks (sidebar + SQLite library) | 2026-09-27 | [`26-09-27_phase13-bookmarks.md`](logs/26-09-27_phase13-bookmarks.md) |
| 14 — Flatpak and AppImage | 2026-09-27 | [`2026-09-27_flatpak-appimage.md`](logs/2026-09-27_flatpak-appimage.md) |

## Other notes

| Note | Date | File |
|---|---|---|
| `MainWindow` split into a mixin package: the chain, and why Pylance needs it | 2026-09-25 | [`26-9-25_refactor.md`](logs/26-9-25_refactor.md) |
| Flat mixins with a declared host contract (Option B) — plan only, postponed | 2026-09-25 | [`flat_mixins_declared_contract_refactor.md`](logs/flat_mixins_declared_contract_refactor.md) |
| Developer environment: chat terminal "was closed" errors, caused by `PROMPT_COMMAND` being clobbered in `~/.bashrc` | 2026-09-25 | [`2026-09-25_vscode-terminal-shell-integration.md`](logs/2026-09-25_vscode-terminal-shell-integration.md) |

## Status

- Phases 1–14 are complete. Phase 13 established the SQLite storage layer
  (`app/core/schema.sql`, `app/core/hashing.py`, `app/core/database.py`), turned the
  Phase 12 notes panel into the tabbed sidebar (`app/ui/sidebar.py`,
  `app/ui/bookmarks_panel.py`, `app/ui/main_window/sidebar.py`), and moved the `Ctrl+B`
  bookmark from an in-memory viewer dict to content-hash-keyed rows in `library.db`.
- The `missing` and `troubleshooting` lists added to `TASKS.md` afterwards are done in the same
  log file: the palette reaches both sidebar tabs (`Show Bookmarks`, `Show Notes`) and creates a
  note (`New Note`), the notes pane has a "+" button with an autosaving editor, a non-writable
  data directory degrades to a temporary library (status-bar notice + `File ▸ Library Location…`
  dialog), and the outline is cached per book and not rebuilt when it has not changed.
- Phase 15 (Markdown notes) is next. Note bodies are created and edited as plain text now, so
  what remains is Markdown rendering, a preview pane, tag parsing, and detecting edits made
  outside the app. The considerations for the rendering phase are recorded in
  `useful_features.md` under `render markdown in the app`.
- Phase 14 is the first log named `YYYY-MM-DD_subject.md` rather than
  `YY-MM-DD_phase#-subject.md`, because `AGENTS.md` mandates that convention for new daily logs;
  the Phase 14 row above is the only one that does not follow the older phase-log pattern.
  `ROADMAP.md` numbers Flatpak/AppImage as Phase 14 and Markdown notes as Phase 15, while
  `TASKS.md` still calls the packaging work "Phase 15".
- Phase 9's `Possible problems` section was stranded at the end of Phase 10 in the old single-file summary; it now sits with Phase 9.
- The `Refactor: Split MainWindow into a Mixin Package` section of the old summary is superseded by `logs/26-9-25_refactor.md`, which covers the same ground in more detail.
