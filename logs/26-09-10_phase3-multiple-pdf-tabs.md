# Phase 3 — Open Multiple PDF in Tabs

**Completed:** 2026-09-10 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

- `main.py` had to change because the single-document version placed one `PDFViewerWidget` directly in `QMainWindow.setCentralWidget()`. A window can have only one central widget, so multiple viewers need a `QTabWidget` container instead.
- To implement the change, create a `QTabWidget`, set it as the central widget, and add one `PDFViewerWidget` per PDF with `addTab()`. Connect `tabCloseRequested` to a method that removes the tab, disposes the viewer, and updates tab-bar visibility.
- Added a native `QTabWidget` containing Alice and Frankenstein at startup.
- The tab bar is hidden for one open document and shown for two or more.
- Individual tabs can be closed without terminating the application.
