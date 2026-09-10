## Phase 1: Create Window

Completed 2026-09-10.

- Confirmed PySide6 `6.11.2` is installed in the local `.venv` environment and already listed in `requirements.txt`.
- Added `app/main.py` with a minimal `QMainWindow` entrypoint.
- The window opens maximized and can be launched with `python -m app.main`.

## Phase 3: Open Multiple PDF in Tabs

Completed 2026-09-10.

- Added a native `QTabWidget` containing Alice and Frankenstein at startup.
- The tab bar is hidden for one open document and shown for two or more.
- Individual tabs can be closed without terminating the application.

## Phase 2: Render PDF in PySide6 Window

Completed 2026-09-10.

- Added a PyMuPDF render engine that opens the bundled Alice PDF and rasterizes only the requested page.
- Added a single-page viewer that fits the active page to the available viewport and rerenders on resize.
- Connected the viewer to the maximized main window.
