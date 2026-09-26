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

## Other notes

| Note | Date | File |
|---|---|---|
| `MainWindow` split into a mixin package: the chain, and why Pylance needs it | 2026-09-25 | [`26-9-25_refactor.md`](logs/26-9-25_refactor.md) |
| Flat mixins with a declared host contract (Option B) — plan only, postponed | 2026-09-25 | [`flat_mixins_declared_contract_refactor.md`](logs/flat_mixins_declared_contract_refactor.md) |
| Developer environment: chat terminal "was closed" errors, caused by `PROMPT_COMMAND` being clobbered in `~/.bashrc` | 2026-09-25 | [`2026-09-25_vscode-terminal-shell-integration.md`](logs/2026-09-25_vscode-terminal-shell-integration.md) |

## Status

- Phases 1–11 are complete. `ROADMAP.md` Phase 12 (bookmarks dock) is next; `TASKS.md` tracks its sub-tasks.
- Phase 9's `Possible problems` section was stranded at the end of Phase 10 in the old single-file summary; it now sits with Phase 9.
- The `Refactor: Split MainWindow into a Mixin Package` section of the old summary is superseded by `logs/26-9-25_refactor.md`, which covers the same ground in more detail.
