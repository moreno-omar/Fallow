# Phase 6 — Dialog to Pick PDF File

**Completed:** 2026-09-10 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

- created menuBar by using the built-in one from QMainWindow
- Added `File`, `View`, and `Help` menus through `QMainWindow.menuBar()`.
- Added `File > Open` with a `Ctrl+O` shortcut. It opens a `QFileDialog` filtered for PDF files, creates a new viewer tab for the selected file, selects that tab, and saves the updated session.
- The existing `add_pdf()` method remains the single tab-creation path, so files opened from the dialog receive the same rendering, navigation, and session behavior as restored documents.
- Possible improvements include adding menu actions for close and quit, disabling unsupported file selections with a visible error, and populating the currently empty `View` and `Help` menus.
