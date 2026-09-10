## Phase 1: Create Window

Completed 2026-09-10.

- Confirmed PySide6 `6.11.2` is installed in the local `.venv` environment and already listed in `requirements.txt`.
- Added `app/main.py` with a minimal `QMainWindow` entrypoint.
- The window opens maximized and can be launched with `python -m app.main`.


## Phase 2: Render PDF in PySide6 Window

Completed 2026-09-10.

- Added a PyMuPDF render engine that opens the bundled Alice PDF and rasterizes only the requested page.
- Added a single-page viewer that fits the active page to the available viewport and rerenders on resize.
- Connected the viewer to the maximized main window.

## Phase 3: Open Multiple PDF in Tabs

Completed 2026-09-10.

- `main.py` had to change because the single-document version placed one `PDFViewerWidget` directly in `QMainWindow.setCentralWidget()`. A window can have only one central widget, so multiple viewers need a `QTabWidget` container instead.
- To implement the change, create a `QTabWidget`, set it as the central widget, and add one `PDFViewerWidget` per PDF with `addTab()`. Connect `tabCloseRequested` to a method that removes the tab, disposes the viewer, and updates tab-bar visibility.
- Added a native `QTabWidget` containing Alice and Frankenstein at startup.
- The tab bar is hidden for one open document and shown for two or more.
- Individual tabs can be closed without terminating the application.

## Phase 4: Save Session

Completed 2026-09-10.

- `SessionManager` replaced the hard-coded startup PDF list in `main.py`. That list could open the initial documents but could not remember which files, pages, or tab were active after the application closed.
- It was needed to keep JSON file storage, XDG path selection, type validation, missing-file checks, and session restoration separate from the window's tab-management code.
- Added `SessionManager` to persist the active tab, open absolute PDF paths, and each viewer's current page as JSON.
- The session is stored at `$XDG_CONFIG_HOME/linux-pdf-reader/session.json`, falling back to `~/.config/linux-pdf-reader/session.json`.
- Startup validates saved entries and existing files before restoring tabs; missing or malformed entries are skipped safely.
- Session state is saved when a tab closes and when the main window closes. A future improvement would be to centralize viewer state accessors instead of reading the viewer's internal disposal flag during serialization.

## Phase 5: Preferred PDF Settings

Completed 2026-09-10.

- Kept the viewer in strict single-page mode: each tab renders only its active page.
- The existing renderer fits that page inside the viewport using one uniform scale, preserving the PDF aspect ratio and recalculating after resize.
- Added `QShortcut` bindings for Right/Down/Page Down and Left/Up/Page Up, with boundary checks so navigation changes by one page only.
- Added wheel-event routing from the scroll area and viewport. Wheel angle deltas are accumulated into 120-unit detents, and each detent moves exactly one page.
- These controls belong to `PDFViewerWidget`, so every tab keeps independent page state. Possible improvements include a visible page counter, configurable key bindings, and handling high-resolution pixel-delta wheel devices separately.

## Phase 6: Dialog to Pick PDF File

Completed 2026-09-10.

- created menuBar by using the built-in one from QMainWindow
- Added `File`, `View`, and `Help` menus through `QMainWindow.menuBar()`.
- Added `File > Open` with a `Ctrl+O` shortcut. It opens a `QFileDialog` filtered for PDF files, creates a new viewer tab for the selected file, selects that tab, and saves the updated session.
- The existing `add_pdf()` method remains the single tab-creation path, so files opened from the dialog receive the same rendering, navigation, and session behavior as restored documents.
- Possible improvements include adding menu actions for close and quit, disabling unsupported file selections with a visible error, and populating the currently empty `View` and `Help` menus.
