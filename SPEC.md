# SPEC.md - Linux PDF Reader

## Project Overview
A lightweight, open-source Linux desktop document viewer written in Python. The application provides a focused, single-page reading experience for local PDF files with tabbed navigation, persistent reading sessions, and theme toggling.

- **Intended Users:** Linux desktop users who require a fast, distraction-free document reader for sequential reading without editing clutter.
- **Problem Solved:** Most mainstream Linux viewers either carry heavy document-authoring dependencies, lack reliable multi-tab state restoration across restarts, or fail to provide a dedicated dark mode canvas inversion optimized for low-light reading.

---

## Required Behavior & User Experience

### 1. Document Display & Viewport
- **Single Page View:** Displays one page at a time with strict single-page rendering.
- **Fit-to-Page Magnification:** Automatically scales the active page Pixmap to fit within the viewport window dimensions while strictly maintaining the document aspect ratio. Page scale dynamically recalculates on viewport resize events.

### 2. Tabbed Document Navigation
- **Multi-Tab Interface:** Allows multiple PDF documents to be open concurrently in individual tabs via a native tab widget.
- **Independent Tab State:** Each tab maintains its own file path reference, current page index, total page count, and zoom/aspect cache.
- **Tab Lifecycle:** Tabs can be opened via a file picker dialog or closed individually without terminating the application process.

### 3. Page Turning & Input Controls
- **Keyboard Navigation:**
  - `Next Page`: `Right Arrow`, `Down Arrow`, or `Page Down`.
  - `Previous Page`: `Left Arrow`, `Up Arrow`, or `Page Up`.
- **Mouse Wheel Navigation:**
  - `Scroll Down`: Increments to the next page.
  - `Scroll Up`: Decrements to the previous page.
  - Event debouncing / boundary checks ensure single page steps per discreet wheel detent and prevent out-of-range navigation at document boundaries.

### 4. Theming (Dark Mode)
- **UI Chrome:** Dark QSS stylesheet applying neutral dark tones (`#1e1e2e` / `#2b2b2b`) to tab bars, frame backgrounds, and borders.
- **Page Content Inversion:** When dark mode is active, PyMuPDF pixmap color channels are inverted prior to rendering to prevent glaring white page backgrounds in low-light environments.
- **Toggle Mechanism:** Accessible via keyboard shortcut (`Ctrl+D`) and a dedicated toolbar toggle button.

### 5. Session Persistence
- **State Capture:** Automatically saves session state upon application exit or document load/close.
- **Session File Location:** Stored in compliance with the XDG Base Directory specification at `$XDG_CONFIG_HOME/linux-pdf-reader/session.json` (falling back to `~/.config/linux-pdf-reader/session.json`).
- **Persisted Schema:**
  - `active_tab_index`: Integer pointer to the tab active at exit.
  - `dark_mode`: Boolean flag storing theme preference.
  - `tabs`: Array of objects containing:
    - `file_path`: Absolute path string.
    - `current_page`: 0-indexed integer of the last viewed page.
- **Session Recovery:** On startup, verifies file existence; existing files are restored to their exact recorded page positions, while missing/deleted files are pruned gracefully.

---

## Architecture & Major Components

```
+-------------------------------------------------------------+
|                        CLI / Entrypoint                     |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                  MainWindow (PySide6 QMainWindow)           |
|  - Manages QTabWidget, Shortcuts, Theme State, Resize Events |
+-------------------------------------------------------------+
         |                                           |
         v                                           v
+-----------------------+                 +---------------------+
|    PDFViewerWidget    |                 |   SessionManager    |
| (QScrollArea/QLabel)  |                 | (JSON Serialization)|
| - Event Filter        |                 | - Load / Save State |
| - Wheel / Key Routing |                 | - XDG Config Path   |
+-----------------------+                 +---------------------+
         |
         v
+-----------------------+
|  RenderEngine (fitz)  |
| - PyMuPDF Page Raster |
| - Pixmap Inversion    |
| - Scale Calculation   |
+-----------------------+
```

### Module Breakdown
- **`app/main.py`:** Initializes the `QApplication`, parses optional initial CLI file arguments, and launches `MainWindow`.
- **`app/ui/main_window.py`:** Primary window container managing the tab bar, keyboard shortcuts, menu/actions, and theme switching.
- **`app/ui/viewer_tab.py`:** Individual tab container hosting the rendered page canvas, handling viewport resize recalculations and routing navigation events.
- **`app/core/pdf_engine.py`:** PyMuPDF (`fitz`) interface responsible for opening document handles, querying page dimensions, extracting pixmaps, and performing color inversions.
- **`app/core/session.py`:** Manages serialization and deserialization of application state to the local JSON configuration file.

---

## Supported Tool & Dependency Versions
- **Operating System:** Linux (tested on modern desktop environments running X11 or Wayland).
- **Python Runtime:** Python `>= 3.10`
- **Primary Dependencies:**
  - `PySide6 >= 6.5.0` (Official Qt 6 Python bindings)
  - `PyMuPDF >= 1.23.0` (High-performance PDF rendering engine)
- **Standard Library Modules:** `pathlib`, `json`, `sys`, `os`, `argparse`

---

## Security & Privacy Requirements
- **Strictly Local & Offline:** The application does not instantiate network sockets, initiate HTTP/HTTPS requests, or embed telemetry tracking.
- **File System Boundary:** Accesses only explicit file paths opened by the user via file picker dialog, CLI argument, or the saved session file.
- **Defensive Deserialization:** The session manager validates all JSON types and verifies `pathlib.Path(file_path).is_file()` before dispatching file open calls to prevent crashes or unexpected state injection.

---

## Non-Goals
- **Document Editing:** No support for text edits, annotations, form entry, digital signatures, or page reordering.
- **Cross-Platform Targeting:** No official builds, packaging, or compatibility workarounds for Microsoft Windows or Apple macOS.
- **DRM & Monetization:** No licensing checks, locked features, account requirements, or paid subscription tiers.


---

## Future Enhancements (Nice-to-Have)
- Extended ebook container parsing (e.g., EPUB, CBZ/CBR via PyMuPDF).
- Alternative view modes (dual-page side-by-side spread, continuous vertical ribbon).
- Configurable shortcut bindings via JSON configuration.
- Thumbnail sidebar navigation panel.
- Continuous multi-page vertical scrolling is intentionally excluded in favor of single-page pagination.

---

## Acceptance Criteria
1. **Launch & Standalone Execution:** Application starts cleanly within a virtual environment on Linux without external runtime errors.
2. **Tabbed Multi-Document Handling:** Users can open at least 5 different PDF documents across distinct tabs, switch between them, and close individual tabs.
3. **Discrete Navigation:** Pressing navigation keys (`Left`/`Right`/`Up`/`Down`) or rolling the mouse wheel advances or rewinds the document by exactly one page at a time.
4. **Magnification Fidelity:** PDF pages render crisply and automatically scale to fill the visible tab viewport without letterbox clipping or distortion.
5. **Dark Mode Performance:** Switching dark mode toggles the Qt widget stylesheet and inverts the rendered PDF canvas colors within 100 milliseconds without reloading the document.
6. **Session Restoration:** Quitting the application via `Ctrl+Q` or window close and subsequently relaunching it automatically reopens all previous documents at the exact page index where the user left off.
