# Phase 11 — Tabs

**Completed:** 2026-09-24 · **Index:** [`SUMMARY.md`](../SUMMARY.md)

**What was added**

- `app/ui/document_tabs.py` holds the three pieces of the tab strip:
  - `DocumentTabBar(QTabBar)` — width-clamped tabs, ellipsis eliding, and a sliding five-tab window.
  - `TabOverflowButton(QToolButton)` — the dropdown at the end of the tab bar that lists every open document.
  - `TabSearchDialog(CommandPalette)` — the `Ctrl+Shift+A` list of open documents.
  - `TabEntry` — a frozen record (`index`, `title`, `location`, `page`, `page_count`, `active`) describing one open document for those lists.
- `MainWindow` wires them up: it swaps in the custom tab bar, puts the overflow button in the `TopRightCorner`, adds `View > Tab Search` (`Ctrl+Shift+A`), sets a per-tab tooltip, and gained `tab_entries()`, `tab_commands()`, `focus_tab()`, and `refresh_tab_window()`.

**Why it is split this way**

The widgets describe and report; the window acts. `TabOverflowButton` receives an `entries_provider` callable and rebuilds its menu on `aboutToShow`, and `TabSearchDialog` is the same palette the command palette uses, only with a different title, placeholder, and row cap. That keeps tab behaviour (which widget is current, how a tab closes) in one place and lets a simpler version of this feature be: hide tabs past the fifth, show a `QMenu` with one action per tab, and return the chosen index after the dialog closes.

**How the width limits work**

- `tabSizeHint()` clamps every tab to 90–190px. Qt elides the title with an ellipsis to whatever width the tab ends up with (`setElideMode(ElideRight)`), so ~20 characters stay readable while the full name lives in the tab tooltip.
- Qt **shrinks** tabs to fit a tab bar instead of overflowing it, so a narrow bar would squeeze eight documents into 119px each and never show scroll arrows. Two measures prevent that:
  - the bar's `maximumWidth` is set to `5 × MAX_TAB_WIDTH` (950px), and
  - `sync_visible_window()` hides everything outside a five-tab window that always contains the active tab, revealing before hiding so Qt never re-picks the current tab. The window only slides as far as needed (active tab 4 of 8 shows 0–4, active tab 7 shows 3–7).
- With at most five tabs in the bar, titles keep their 90–190px width; if the *window* is narrower than five minimum tabs, Qt's scroll arrows appear as required.

**Tab Search**

`MainWindow.tab_commands()` builds one `Command` per open document whose handler is `partial(self.focus_tab, entry.index)`, so Tab Search runs through exactly the same "accept, then run the handler after `exec()` returns" path as the command palette. The row's right-hand hint is the reading position (`page 12 of 340`), and `MAX_RESULTS` is raised from 8 to 20 so the dialog can show the documents the tab bar is hiding. `focus_tab()` slides the visible window onto the target *before* `setCurrentIndex()`.

**Verification**

- A throwaway offscreen script confirmed: the tab bar is a `DocumentTabBar` with `ElideRight`, scroll buttons on, and a 950px budget; with 8 documents exactly 5 tabs are visible and their widths stay in 90–190px; focusing tab 7 slides the window to 3–7 without changing the current index; tooltips hold the absolute path; the overflow button is the `TopRightCorner` widget, lists all 8 documents with full titles and a checkmark on the active one, and focusing from the menu moves the selection and the window; a 400px bar keeps tabs at ≥90px; the strip hides again with one document; `Tab Search` exists as a menu action with `Ctrl+Shift+A`, is collected by the command palette exactly once, and its dialog filters, selects the highlighted row on Enter, focuses that document, and reports nothing when dismissed. All checks passed.
- `window.grab()` snapshots in both themes confirmed the ellipsis (`Frankenstein Or The M…`), the five-tab window, the dropdown arrow at the end of the bar, the dark overflow menu with all document names, and the Tab Search dialog with page positions.

### Suggestions (to improve)

- Mark the hidden documents in the tab bar itself, for example a small count badge on the overflow button (`▾ 3`) so it is obvious how many tabs are off-screen.
- Add a "Close Others" / "Close All" entry to the overflow menu and a middle-click-to-close on tabs, which is what most readers expect from a tab strip.
- Show the file's parent folder in Tab Search rows when two documents share a name (two copies of `report.pdf` are currently indistinguishable in the list).
- Reorder or pin tabs: `setMovable(True)` plus a persisted order would let a user keep reference documents at a fixed position.
- Restore the session's zoom level per document while the session format is being touched for Phase 12.

### Possible problems

- Hiding tabs relies on `QTabBar.setTabVisible`; the window is recomputed on add, close, and `currentChanged`. Code that calls `tabs.setCurrentIndex()` directly (bypassing `focus_tab()`) can momentarily activate a hidden tab, so new jump-to-tab code should go through `focus_tab()`.
- The sliding window is recomputed from the current index only. If a tab is inserted in the middle of a long strip (nothing does that today; `add_pdf` always appends), the window would jump rather than stay put.
- `TabSearchDialog.MAX_RESULTS = 20` again silently truncates a strip with more than 20 documents; the overflow menu remains the complete list.
- The five-tab window is a fixed constant. On a very wide monitor five 190px tabs look sparse, and on a small laptop five tabs plus the overflow button may still need scroll arrows, so the number is a compromise rather than a fit to the available width.
- Tab titles are still derived from the file name (`tab_title()`), so two documents whose stems match produce identical tab labels and identical Tab Search rows; only the tooltip and the row tooltip tell them apart.
