# Phase 9 — Useful Keyboard Shortcuts

**Completed:** 2026-09-24 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

- Shortcuts live in three places, because a keyboard shortcut must be reachable no matter which widget holds focus:
  - Window-level `QAction`s in the menu bar (`Ctrl+W`, `Ctrl+Q`, `Ctrl+F`, `Ctrl+G`, `Ctrl+B`, `Ctrl++`/`Ctrl+=`, `Ctrl+-`, `Ctrl+0`, and the dark-mode keys). Menu actions are used instead of bare `QShortcut`s so Phase 10 can enumerate them for the command palette.
  - One window-level `QShortcut` for `Esc`, which closes the find bar.
  - The viewer's own `Ctrl`+wheel handling inside `eventFilter`, because the wheel arrives at the scroll area, not at the window.
- `Ctrl+Shift+D`, `Alt+D`, and `Ctrl+D` all set the same checkable `View > Dark Mode` action, and `Ctrl+Q` now also exists as `File > Quit`.
- Find (`Ctrl+F`) adds a hidden top `QToolBar` with a query field and a result label. `PDFViewerWidget.find()` asks `RenderEngine.search_page()` (PyMuPDF `Page.search_for`) for page-space rectangles, walks forward through the document, and wraps at the end. Repeated `Enter` advances through the matches on the located page before moving on. Pressing `Esc` hides the bar and drops the highlights.
- Highlight painting happens on the rendered `QImage` with NumPy blending in `RenderEngine.highlight_matches()`. Passive matches are blended softly, the active match is stronger, and dark mode switches the marker palette so highlights never glare. Because rendering already goes through one code path, highlights stay correct after zoom, resize, page turn, or theme change.
- Go to page (`Ctrl+G`) focuses the existing bottom-bar field and selects its text, so the user can type a page number immediately.
- Bookmark (`Ctrl+B`) is the Phase 9 scaffold: `PDFViewerWidget.toggle_bookmark()` stores a pointer from `Document.make_bookmark((0, page))` — PyMuPDF's `(chapter, page)` location pointer, resolvable again with `Document.find_bookmark()` — in a per-viewer dictionary, and the status bar reports the count. Nothing is written to disk yet.
- Zoom stores a magnification factor in the viewer and multiplies the fit-to-viewport scale before building `pymupdf.Matrix(scale, scale)` in `RenderEngine.render_page()`, so `zoom == 1.0` still means fit-to-page. `Ctrl`+wheel steps the factor by 1.15 per wheel detent and clamps it to `0.25`–`4.0`. Above `1.0` the page label gets a minimum size equal to the raster, which is what makes the scroll area show scroll bars instead of clipping the page.

### Suggestions (to improve)

- Route find through a real search field on the document instead of the toolbar, and add "find previous" (`Shift+Enter`) plus a match counter such as `2 of 4`.
- Persist zoom per document in the session JSON the way `current_page` already is, so reopening a document restores the user's magnification.
- Grow the bookmark scaffold into Phase 12: store marks as JSON keyed by file path or SHA-256, seed a bookmark title from the page's first text line, and render them in the planned `QDockWidget` list.

### Possible problems

- Registering the same key sequence twice on one action makes Qt treat the shortcut as an ambiguous overload and silently never fire it. This actually happened with `Ctrl+-`: `QKeySequence.StandardKey.ZoomOut` already resolves to `Ctrl+-` on this desktop, so adding it again broke the binding. `QKeySequence.keyBindings()` is also unsafe for this reason, because the platform theme returned a second, bogus entry (`'Zoom In'`). Explicit, unique sequences are used instead, and the verification script prints every action's shortcut list so duplicates are visible.
- `QSize()` is the invalid size `(-1, -1)`, not `(0, 0)`, so resetting the page label's minimum size needs `QSize(0, 0)`; the placeholder produced a Qt warning on every render.
- Zoom changes the raster's dependency on the viewport size (a scroll bar appearing shrinks the viewport, which changes the fit scale). The current layout converges, but a page whose magnified raster lands exactly on the viewport edge is the case most likely to oscillate, and it is worth re-checking if the label ever stops resizing correctly.
- Find only searches the current page's rasterized text order and always wraps to the top of the document, so a user searching backwards can loop from the end of the file back to the start without warning.
- `Ctrl+D` is kept alongside the requested `Ctrl+Shift+D`/`Alt+D` because `SPEC.md` acceptance criterion 5 names `Ctrl+D`; if the intent is to move fully to the Phase 9 keys, drop it from `MainWindow.DARK_MODE_SHORTCUTS`.
- The bookmark dictionary lives in the viewer and is dropped when a tab closes, so marks are lost on close and are not part of the session file yet.
