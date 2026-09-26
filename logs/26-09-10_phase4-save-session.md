# Phase 4 — Save Session

**Completed:** 2026-09-10 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

- `SessionManager` replaced the hard-coded startup PDF list in `main.py`. That list could open the initial documents but could not remember which files, pages, or tab were active after the application closed.
- It was needed to keep JSON file storage, XDG path selection, type validation, missing-file checks, and session restoration separate from the window's tab-management code.
- Added `SessionManager` to persist the active tab, open absolute PDF paths, and each viewer's current page as JSON.
- The session is stored at `$XDG_CONFIG_HOME/linux-pdf-reader/session.json`, falling back to `~/.config/linux-pdf-reader/session.json`.
- Startup validates saved entries and existing files before restoring tabs; missing or malformed entries are skipped safely.
- Session state is saved when a tab closes and when the main window closes. A future improvement would be to centralize viewer state accessors instead of reading the viewer's internal disposal flag during serialization.
