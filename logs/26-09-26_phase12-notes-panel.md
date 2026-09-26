# Phase 12 — Create Panel to View Notes

**Completed:** 2026-09-26 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

---

## Objective

Implement `ROADMAP.md` Phase 12: a notes panel on the left of the document, held by
a `QSplitter`, defaulting to ~30% of the window (clamped 360–640px), resizable,
toggleable with `Ctrl+Shift+E` / `F9`, reachable from the command palette,
auto-hiding when dragged below ~10%, and remembered across sessions.

The `TASKS.md` sub-tasks for the phase are:

- [x] Use Qspliter to create panel
- [x] Panel defaults to ~30% width on first run, clamped 360–640px
- [x] Enforce minimum widths on both panes (PDF ≥ 400px, notes ≥ 320px)
- [x] Have panel be toggled on/off with `Ctrl+Shift+E` or `F9`
- [x] Register toggle be accessible to command palette
- [x] Auto-hide when dragged below ~10% width; restore last size on toggle
- [x] Persist splitter state across sessions (QSettings)
- [x] Auto-collapse on first run if window width < 900px

---

## Solution

The window's central widget is no longer the tab widget directly: it is now a
horizontal `QSplitter` whose left child is the notes panel and whose right child is
the single `QTabWidget` every existing feature already talks to. Nothing else had to
move — the tab widget keeps its object identity, so `DocumentsMixin`,
`NavigationMixin`, and the session format are untouched.

| File | Change |
|---|---|
| `app/ui/notes_panel.py` | **New.** `NotesPanel(QWidget)`: object name `notesPanel`, a bold "Notes" header, an empty-state label, `WA_StyledBackground` for the dark QSS. |
| `app/ui/main_window/notes.py` | **New.** `NotesMixin` (layer 7): splitter creation, layout rules, drag handling, `QSettings` persistence, `resizeEvent` first-run hook. |
| `app/ui/main_window/window.py` | Removed `setCentralWidget(self.tabs)`; added `self.create_notes_panel()` before `create_menu_bar()`; chain docstring now lists eight layers. |
| `app/ui/main_window/commands.py` | `CommandsMixin` now extends `NotesMixin` (layer 8), gained `NOTES_PANEL_SHORTCUTS = ("Ctrl+Shift+E", "F9")` and `create_notes_panel_action()`; the action is added to `View`. |
| `app/ui/main_window/theme.py` | QSS for `QSplitter`, the handle, `QWidget#notesPanel`, `QLabel#notesHeader`, `QLabel#notesPlaceholder`. |
| `TASKS.md` | All eight sub-tasks checked off. |

### Why `NotesMixin` sits between `DocumentsMixin` and `CommandsMixin`

The mixin chain is ordered by dependency, and the menu layer is the one that wires the
toggle, so the panel has to exist below it. Placing the new layer at 7 (rather than
renumbering the other six) also means only `commands.py`'s "Layer 7" line and the
`window.py` reading list changed. `CommandsMixin` is now layer 8.

### First-run sizing

`default_notes_width(window_width)` is the whole rule and nothing else:

```
window < 900px      -> 0        (auto-collapse: half a page and a notes column do not share 900px)
otherwise           -> clamp(round(window_width * 0.30), 360, 640)
```

It is applied from `resizeEvent` on the first layout event, not during `__init__`:
at construction the splitter has not been sized yet, and the window is
`showMaximized()`-ed right after `__init__` returns. `_notes_first_run` is armed only
when `QSettings` holds no splitter state, so a saved layout is never recomputed from
the window size. `reference_window_width()` takes the largest of the splitter width,
the window width, and the screen's available width, so the 30% is measured against
the maximized window even if the window manager has not delivered the maximize resize
yet.

The panel's own floor (320px) is set with `setMinimumWidth`, and the document pane
keeps a 400px floor plus `setCollapsible(1, False)` so it can never be dragged away.

### Auto-hide without fighting the drag

`splitterMoved` fires many times per drag, so hiding there would fight the handle the
user is still holding. Each move records the position and restarts a 200ms single-shot
`QTimer`; the timer's slot runs once the drag has settled. If the settled position is
below `max(10% of the splitter width, 1px)`, the panel hides itself and the menu
checkmark is corrected (`sync_notes_action()` blocks the action's signals, because the
action's own `toggled` is what calls back into visibility). Only settled widths ≥ 320px
are remembered, so a collapse can never become the size the next toggle restores.

Qt keeps children collapsible by default, which is what makes the 10% path reachable
at all: the handle snaps from the 320px minimum straight to 0, i.e. below the
threshold. (A plain "minimum width" drag would otherwise stop at 320px and the
auto-hide would only ever trigger on windows wider than 3200px.)

### Persistence

`QSettings("linux-pdf-reader", "Fallow PDF Reader")` writes
`$XDG_CONFIG_HOME/linux-pdf-reader/Fallow PDF Reader.conf` — the same directory as
`session.json`, so the app keeps one config folder. Three keys: `notes/splitter_state`
(the raw `QSplitter.saveState()` byte array), `notes/visible`, and `notes/width` (the
last usable pane width, so a restore does not depend on how Qt sized a hidden pane).

---

## Actions Performed

1. Read `AGENTS.md`, `SPEC.md`, `ROADMAP.md`, `TASKS.md`, repo memory, and the whole
   `app/ui/main_window/` package to place the feature in the existing mixin chain.
2. Wrote `app/ui/notes_panel.py` and `app/ui/main_window/notes.py`.
3. Wired the panel into `window.py` (central widget swap), `commands.py` (View menu
   action + shortcut constant), and `theme.py` (dark QSS).
4. Ran the app headlessly with a throwaway offscreen script, redirecting output to
   `/tmp/verify_phase12.out` and reading it with the file reader (the `logs/2026-09-25`
   habit).
5. Fixed two defects found by that script (below) and re-ran until clean.
6. Rendered `window.grab()` snapshots for the panel on/off and both themes, and
   inspected them as images.

### Defects found and fixed by verification

- **`setSizes` scales proportional requests.** `apply_notes_width` originally took the
  window width as the total; a 360px request against a 1200px total on a 792px
  splitter came back as 237px (then clamped to the 320px minimum). Fixed by measuring
  the span from the widget (`splitter_span()`).
- **The handle is not part of the panes.** `sizes()` sums to
  `splitter.width() - handleWidth()`, so a 360px request on a 796px splitter produced
  358px. Fixed by subtracting `handleWidth() * (count - 1)` in `splitter_span()`; a
  360px request now lands on exactly 360 and a remembered width round-trips unchanged.

---

## Verification Output

`QT_QPA_PLATFORM=offscreen`, a temporary `XDG_CONFIG_HOME`, and
`PYTHONPATH=/home/redram/python/Fallow .venv/bin/python /tmp/verify_phase12.py`
(exit code `0`, 44 checks, all passing):

```
screen available width: 800
settings file: /tmp/fallow-phase12-atp2kx3h/linux-pdf-reader/Fallow PDF Reader.conf
window width: 796 splitter width: 796 pane sizes: [0, 796]
handle width: 4 pane span: 792
[PASS] central widget is the splitter
[PASS] notes panel is the left child
[PASS] document tabs are the right child
[PASS] panel minimum width is 320 -> 320
[PASS] document pane minimum width is 400 -> 400
[PASS] right pane cannot be collapsed
[PASS] narrow window has no default width -> 0
[PASS] 1000px window clamps up to 360 -> 360
[PASS] 1400px window is 30% (420) -> 420
[PASS] 4000px window clamps down to 640 -> 640
[PASS] first run auto-collapsed on the 800px screen -> width=796
[PASS] palette exposes Notes Panel exactly once -> 1
[PASS] palette row shows both keys -> Ctrl+Shift+E, F9
[PASS] action carries Ctrl+Shift+E and F9 -> ['Ctrl+Shift+E', 'F9']
[PASS] total palette entries -> 14
[PASS] no shortcut collision -> ['Alt+D', 'Ctrl++', ..., 'Ctrl+Shift+D', 'Ctrl+W']
[PASS] toggle shows the panel
[PASS] shown pane respects the 320px minimum -> [360, 432]
[PASS] toggle hides the panel
[PASS] last size restored on toggle -> [360, 432] vs 360
[info] F9 sent to the window handle toggled the panel: True
[PASS] drag below 10% auto-hides the panel
[PASS] action unchecked after auto-hide
[PASS] auto-hide keeps the last usable width -> 360 vs 360
[PASS] toggle restores the pre-drag width -> [360, 432] vs 360
[PASS] kept drag width is tracked -> 380
[PASS] apply_default_notes_layout(1200) shows a 360px pane -> [360, 432]
[PASS] second run restores the pane width -> [380, 412]
[PASS] second run restores visibility
[PASS] hidden state survives a restart
[PASS] hidden state keeps the action unchecked
[PASS] first run does not clobber the stored layout
all checks passed
```

Notes on the run:

- The offscreen screen is 800px wide, so the *first* run on this machine exercises the
  narrow-window rule (auto-collapse) rather than the 30% rule. The 30% rule and both
  clamps are covered by `default_notes_width()` directly, and by
  `apply_default_notes_layout(1200)` / `(800)` / `(4000)` end to end.
- **The `F9` key click is real, not an `action.trigger()` stand-in.**
  `QTest.keyClick(window, Qt.Key_F9)` does nothing, because sending a key event
  straight to a `QWidget` skips the shortcut map. `QTest.keyClick(window.windowHandle(),
  Qt.Key_F9)` goes through `QWidgetWindow::handleKeyEvent`, fires the action, and the
  panel toggled both ways.
- Snapshots (`window.grab()`) confirmed the dark theme panel (#292E39 background, ice
  header, muted placeholder, lighter splitter handle), the light theme, and that a
  hidden panel leaves no handle and no leftover edge — the tab widget simply fills the
  window.

---

## References Used

1. `QSplitter` class reference — `saveState`/`restoreState`, `setSizes`, `sizes`,
   `childrenCollapsible`, `handleWidth`, `splitterMoved`:
   <https://doc.qt.io/qt-6/qsplitter.html>
2. `QSettings` (PySide6) — organisation/application scoping, `value()` with a type,
   and the XDG config path on Linux:
   <https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSettings.html>
3. `QAction` class reference — checkable actions, `setShortcuts`, shortcut context,
   ambiguity, and `blockSignals` interaction with `toggled`:
   <https://doc.qt.io/qt-6/qaction.html>

---

## Optional steps

- Put the notes pane behind a `View > Layout` submenu together with a "Reset Notes
  Width" entry, mirroring `Reset Zoom` (`Ctrl+0`), so a user who drags the pane to
  something unusable has a one-click way back to the 30% default.
- Add a `QSettings` key for the panel's default ratio so the 30%/360–640 numbers live
  in configuration rather than in constants.
- Give `NotesPanel` a vertical splitter of its own once Phase 13 adds a note list above
  the Markdown editor, so the list and the editor are independently resizable.
- Store the layout under `notes/geometry_version` so a future change to the splitter's
  child count can invalidate an old `splitter_state` byte array explicitly instead of
  relying on `restoreState()` returning `False`.

## Possible problems

- **`QSettings` write frequency.** `save_notes_settings()` runs on every settled drag,
  every toggle, and the first run — each call rewrites three keys, and `splitter_state`
  is a byte array. It is a few hundred bytes on a local `.conf` file and the debounce
  keeps it to one write per drag, but if more panel state is added this should move to
  a `QSettings` instance that is left to flush on destruction.
- **The 10% threshold is compared against the settled position only.** A drag that
  ends 1px above the threshold stays visible, and one that ends 1px below hides. There
  is deliberately no hysteresis, so a user can land on the edge and see the panel snap
  shut; a two-threshold (hide at 8%, show again at 12%) rule would remove that.
- **Restoring `splitter_state` on a differently sized window** lets Qt scale the saved
  sizes to the new span, so `notes/width` and the actual pane can disagree after a
  monitor change. The stored width is applied on the next toggle, which repairs it, but
  the first frame after such a start may not be exactly the remembered width.
- **`reference_window_width()` prefers the largest of three values.** In a
  multi-monitor setup where the window opens maximized on a secondary screen but
  `self.screen()` resolves to a wider primary screen, the first-run panel can be sized
  against the wrong screen — bounded by the 640px clamp, so the worst case is a 64px
  difference.
- **The panel is a container only.** Until Phase 13 fills it, the pane shows a fixed
  placeholder for every document; it does not react to the active tab, so switching
  tabs cannot yet change what the panel displays.
- **`NotesMixin` declares `notes_action` as `QAction | None = None`** because the
  action is created one layer *above* it. If `CommandsMixin`'s `create_menu_bar()` is
  ever reordered after the panel is shown, the checkmark would be missing until the
  next toggle; the `None` guard keeps that from crashing, but the coupling is
  invisible in the type signature.
