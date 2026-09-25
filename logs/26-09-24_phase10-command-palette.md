# Phase 10 — Create Command Palette

**Completed:** 2026-09-24 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

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
