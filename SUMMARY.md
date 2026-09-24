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

## Phase 7: Useful Bottom Bar

Completed 2026-09-10.

- Added a non-movable bottom `QToolBar` with expanding spacers that keep its page controls centered.
- Added a validated page-number field and a `current of total` status label for the active PDF tab.
- Added page-change signaling from each viewer so arrow keys, wheel navigation, tab switching, and direct page entry keep the controls synchronized.
- Page entry uses one-based display numbers while the viewer continues to store zero-based page indexes. Possible improvements include a visible Go button, focus-friendly page validation feedback, and previous/next toolbar buttons.

## Phase 8: Dark Mode

Completed 2026-09-10.

- Added a checkable `View > Dark Mode` action. Dark mode is enabled by default and can be restored from session JSON.
- Applied a Nord/slate UI palette using `#2E3440` for backgrounds and `#ECEFF4` for default text.
- Added HSL pixel transformation in `RenderEngine`: near-white low-saturation paper becomes slate, near-black body text becomes ice, and colored pixels retain hue and saturation while their lightness is clamped to $0.55 \le L \le 0.75$.
- Each viewer rerenders its active page when the theme changes, without reopening the PDF.
- Possible improvements include moving pixel processing to a worker for very large pages, caching transformed pages, and adding contrast-aware handling for images and transparency.
- Replaced the Python per-pixel loop with NumPy array operations and a precomputed 256-entry RGB LUT for neutral pixels. The LUT maps ice text to slate paper through a smooth cubic curve, preserving grayscale antialiasing levels instead of flattening font edges.
- Colored pixels are transformed in bulk with their hue and saturation retained; lightness moves smoothly into the readable midrange rather than being hard-clipped at the endpoints. This reduces UI lag and avoids destroying subpixel edge relationships.
- Replaced the colored-pixel cutoff with continuous chroma blending: pixels transition smoothly from the grayscale LUT at chroma 15 to hue-safe inverted colors at chroma 55, using smoothstep interpolation for antialiased syntax edges.

## Phase 9: Useful Keyboard Shortcuts

Completed 2026-09-24.

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


## Phase 10: Create Command Palette

Completed 2026-09-24.

**What was added**

- `app/ui/command_palette.py` holds two small pieces: a frozen `Command` dataclass (`title`, `shortcut`, `handler`) and the `CommandPalette(QDialog)` that lists and filters those records.
- `app/main.py` gained a `View > Command Palette` action bound to `Ctrl+P`, plus the methods that build the command list and run the chosen command.

**Why it is split this way**

The dialog knows nothing about PDFs, tabs, or zoom. It only filters records and returns the one the user picked, so all behaviour stays in `MainWindow`. A simpler version of this feature is: build a list of `(label, callable)` pairs, show it in a `QDialog` with a `QLineEdit` above a `QListWidget`, and call the callable after the dialog closes.

**How the commands are collected**

- `menu_actions()` walks the menu bar (`self.menuBar().actions()` → each `menu.actions()`) and skips separators and the palette action itself. This works because Phase 9 deliberately created the shortcuts as menu `QAction`s instead of bare `QShortcut`s — an action already carries a label, a shortcut, and a `trigger()` slot, which is exactly the three fields a palette entry needs.
- `action_command()` converts one action, joining `action.shortcuts()` (dark mode has three keys, zoom-in has two) into one readable label with `QKeySequence.SequenceFormat.NativeText`.
- `viewer_commands()` adds the two entries the menu bar cannot see: page turning, which lives as per-widget `QShortcut`s inside `PDFViewerWidget`. These get a plain description ("Right / Down / Page Down") instead of a `QKeySequence`.
- Result: 12 commands — `Open`, `Close Tab`, `Quit`, `Find`, `Go to Page`, `Bookmark Page`, `Dark Mode`, `Zoom In`, `Zoom Out`, `Reset Zoom`, `Next Page`, `Previous Page`.

**How filtering works**

- `fuzzy_score(query, text)` checks whether the query characters appear **in order** inside the text (so `dm` matches "Dark Mode", `gtp` matches "Go to Page"). It scores contiguous runs higher, adds a bonus for a character that starts a word, adds 25 for an exact prefix, and returns `-1` for no match.
- `score_command()` takes the better of the title score and a shortcut score (the query and label both have `+` stripped, so `ctrl+g` works). Shortcut hits are scored 6 points lower so a real title match still wins.
- Ties break on original menu order, so the list never shuffles for no reason.
- `MAX_RESULTS = 8` caps the list, and `_fit_list_height()` sets the list's fixed height from `sizeHintForRow(0) × rows`, so the dialog grows and shrinks with the result count instead of scrolling.

**Keyboard behaviour**

- `Ctrl+P` on the menu action opens the dialog. It is a window-level action, so it works no matter which widget has focus.
- `Esc` needs no code: `QDialog` already treats it as the reject key, so `exec()` returns `Rejected` and `selected_command` stays `None`.
- `result_list` uses `setFocusPolicy(NoFocus)` so the highlight stays visible while the `QLineEdit` keeps the keyboard. The row widgets are marked `WA_TransparentForMouseEvents` so a click on a row label still reaches the list and fires `itemClicked`.
- An `eventFilter` on the query field intercepts `Up`/`Down`/`PageUp`/`PageDown` and forwards them to `move_selection()`, and catches `Return`/`Enter` to call `run_current()`. Without the filter, the arrow keys would be swallowed by the text field.
- `refresh_results()` always sets `currentRow(0)` after filtering, so the best match is pre-highlighted and `Enter` selects it immediately.
- The palette is frameless and window-modal, and `center_on_parent()` places it in the upper third of the main window on every `showEvent`.
- The dialog styles itself from a `dark_mode` flag passed in by the window (`_stylesheet()`), so it matches the Nord palette in dark mode without adding `QDialog` rules to the main window's global stylesheet.

**Verification**

- A throwaway offscreen script (`QT_QPA_PLATFORM=offscreen`) confirmed: `Ctrl+P` is bound, 12 commands are collected with no duplicate titles, the palette action excludes itself, fuzzy scoring prefers prefixes and rejects non-matches, `dm` filters straight to "Dark Mode", `zoom` lists three matches, Down/Up move the highlight, `Enter` accepts the highlighted row, `Esc` rejects, and every handler really performs its action (page turn, focus the page field, show the find bar, bookmark, zoom in, reset zoom, toggle theme, close a tab). All checks passed.
- Two checks initially "failed" for harness reasons, not code reasons: `zoom` legitimately matches three commands (including "Reset Zoom"), and `hasFocus()` is always `False` under the offscreen platform because no window becomes active — so the focus test compares `focusWidget()` instead.

### Suggestions (to improve)

- Add a `>` prefix convention and a second mode for jumping to a page number or a heading, the way VS Code mixes commands and files in one palette.
- Show the command's menu path ("View ▸ Reset Zoom") and grey out commands that cannot run with no document open (for example "Close Tab").
- Remember the last executed command and float it to the top when the query is empty.
- Add `Up`/`Down` wrap-around, `Tab` completion, and a visible hint row such as "↑↓ to navigate, Enter to run, Esc to close".

### Possible problems

- The palette is rebuilt on every `Ctrl+P` and reads `self.menuBar().actions()`. Any future shortcut created as a bare `QShortcut` — or added after `create_menu_bar()` — will not appear; register new shortcuts as menu actions instead.
- `Command.handler` is a bound method captured at collection time. A command closing its own tab (or quitting) while the handler list is still alive is safe here because the handler runs only after `exec()` returns, but a handler that destroys the window during the call would leave the palette object dangling.
- The dark-mode entry is a checkable action: `trigger()` toggles it, so the palette cannot be used to *set* dark mode explicitly, only to flip it. The list label will also not show the current on/off state.
- `MAX_RESULTS = 8` silently hides the 9th and later match; a very generic query can make a real command unreachable until the user types more letters.
- Frameless dialogs depend on the window manager granting keyboard focus to a child window. It works on the tested X11/Wayland setups; if a tiling WM refuses focus, the palette would appear but not accept typing, and the fix would be to drop `FramelessWindowHint`.
- Centralize shortcut definitions in one mapping so a future JSON-configurable binding table (already listed as a nice-to-have in `SPEC.md`) only has to read that mapping.

### Possible problems

- Registering the same key sequence twice on one action makes Qt treat the shortcut as an ambiguous overload and silently never fire it. This actually happened with `Ctrl+-`: `QKeySequence.StandardKey.ZoomOut` already resolves to `Ctrl+-` on this desktop, so adding it again broke the binding. `QKeySequence.keyBindings()` is also unsafe for this reason, because the platform theme returned a second, bogus entry (`'Zoom In'`). Explicit, unique sequences are used instead, and the verification script prints every action's shortcut list so duplicates are visible.
- `QSize()` is the invalid size `(-1, -1)`, not `(0, 0)`, so resetting the page label's minimum size needs `QSize(0, 0)`; the placeholder produced a Qt warning on every render.
- Zoom changes the raster's dependency on the viewport size (a scroll bar appearing shrinks the viewport, which changes the fit scale). The current layout converges, but a page whose magnified raster lands exactly on the viewport edge is the case most likely to oscillate, and it is worth re-checking if the label ever stops resizing correctly.
- Find only searches the current page's rasterized text order and always wraps to the top of the document, so a user searching backwards can loop from the end of the file back to the start without warning.
- `Ctrl+D` is kept alongside the requested `Ctrl+Shift+D`/`Alt+D` because `SPEC.md` acceptance criterion 5 names `Ctrl+D`; if the intent is to move fully to the Phase 9 keys, drop it from `MainWindow.DARK_MODE_SHORTCUTS`.
- The bookmark dictionary lives in the viewer and is dropped when a tab closes, so marks are lost on close and are not part of the session file yet.
