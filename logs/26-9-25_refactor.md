# Refactor log — splitting `MainWindow` into a mixin package

**Date:** 2026-09-25
**Status:** done and verified
**Scope:** `app/main.py` (537 lines) → `app/main.py` (23 lines) + the `app/ui/main_window/` package (702 lines)

---

## 1. Why this was done

`MainWindow` had 46 methods covering six unrelated concerns: dark mode, in-document
find, bookmarks, page navigation and zoom, document/tab lifecycle, and the menu
bar plus command palette. Reading one feature meant scrolling past five others,
and the file's 537 lines made "where does a shortcut live?" a genuine question.

The goal was comprehension, not new behaviour: **not one method body, constant, or
docstring was rewritten during the move.** The only new code is what the new file
layout forced (section 6).

---

## 2. Before and after

| | Before | After |
|---|---|---|
| Files | `app/main.py` | `app/main.py` + `app/ui/main_window/` (9 files) |
| Largest file | 537 lines | 158 lines (`documents.py`) |
| Shortest meaningful unit | 537 lines | 30 lines (`bookmarks.py`) |
| `MainWindow` methods | 46 | 1 (`__init__`) |
| Entry point | defines the window | 23 lines: `QApplication`, window, event loop |

Total grew from 537 to 725 lines. That difference is module docstrings, imports,
and the shared-state declarations — documents, not logic. No file is longer than
~160 lines, and each answers one question.

---

## 3. What each file does

| File | Lines | Class | Responsibility |
|---|---|---|---|
| `app/main.py` | 23 | — | Creates `QApplication`, shows `MainWindow`, runs `application.exec()`. Nothing else. |
| `main_window/__init__.py` | 12 | — | Re-exports `MainWindow`, so callers write `from app.ui.main_window import MainWindow`. |
| `main_window/base.py` | 53 | `WindowBase` | The shared state every layer uses (`tabs`, `session_manager`, `dark_mode`, `dark_mode_action`, `palette_action`, `overflow_button`, `STATUS_TIMEOUT_MS`) plus the window lifecycle: `save_session()`, `quit_application()`, `closeEvent()`. |
| `main_window/theme.py` | 46 | `ThemeMixin` | `set_dark_mode()` and `apply_theme()`: the QSS stylesheet plus pushing the new theme into every open viewer. |
| `main_window/find.py` | 84 | `FindMixin` | The hidden top `QToolBar`, `show_find_bar()`, `hide_find_bar()`, `find_next()`, and the only window-level `QShortcut` (`Esc`). |
| `main_window/bookmarks.py` | 30 | `BookmarksMixin` | `toggle_bookmark()` — the Phase 9 scaffold, kept as its own file because Phase 12's JSON store and dock belong here. |
| `main_window/navigation.py` | 123 | `NavigationMixin` | The bottom page bar, `current_viewer()` (one place that answers "which document is active?"), page turning, and `zoom_in`/`zoom_out`/`reset_zoom`, `show_zoom`. |
| `main_window/documents.py` | 158 | `DocumentsMixin` | Document lifecycle: `create_open_action()`, `open_pdf_dialog()`, `add_pdf()`, `tab_title()`, `close_tab()`, `close_current_tab()`, `update_tab_bar_visibility()`, `focus_tab()`, `refresh_tab_window()`, `tab_entries()`, `tab_commands()`, `show_tab_search()`. |
| `main_window/commands.py` | 131 | `CommandsMixin` | Menus and shortcuts: the four shortcut constant tuples, `create_action()`, `create_menu_bar()`, the two zoom actions, and the command-palette side (`menu_actions()`, `action_command()`, `viewer_commands()`, `collect_commands()`, `show_command_palette()`). |
| `main_window/window.py` | 65 | `MainWindow` | `__init__` only: build the tab widget, restore the session, call each layer's setup method, apply the theme, `showMaximized()`. |

### Where each old method went

- **Theme:** `set_dark_mode`, `apply_theme` → `theme.py`
- **Find:** `create_find_bar`, `create_shortcuts`, `show_find_bar`, `hide_find_bar`, `find_next` → `find.py`
- **Bookmarks:** `toggle_bookmark` → `bookmarks.py`
- **Navigation:** `create_bottom_bar`, `connect_viewer`, `update_page_controls`, `update_page_status`, `go_to_page`, `focus_page_input`, `current_viewer`, `next_page`, `previous_page`, `zoom_in`, `zoom_out`, `reset_zoom`, `show_zoom` → `navigation.py`
- **Documents:** `create_open_action`, `open_pdf_dialog`, `add_pdf`, `tab_title`, `close_current_tab`, `close_tab`, `update_tab_bar_visibility`, `focus_tab`, `refresh_tab_window`, `tab_entries`, `tab_commands`, `show_tab_search` → `documents.py`
- **Commands:** `create_action`, `create_menu_bar`, `create_zoom_in_action`, `create_zoom_out_action`, `show_command_palette`, `collect_commands`, `menu_actions`, `action_command`, `viewer_commands` → `commands.py`
- **Base:** `save_session`, `closeEvent`, `quit_application` → `base.py`

---

## 4. How the files are connected

### 4.1 The layer chain

The mixins inherit **each other**, in dependency order, with `MainWindow` at the top:

```
MainWindow                         window.py
  └─ CommandsMixin                 commands.py    (menus, shortcuts, palette)
       └─ DocumentsMixin           documents.py   (tabs, open/close, Tab Search)
            └─ NavigationMixin     navigation.py  (page bar, page turn, zoom)
                 └─ BookmarksMixin bookmarks.py   (bookmark toggle)
                      └─ FindMixin find.py       (find bar, Esc)
                           └─ ThemeMixin theme.py (dark mode)
                                └─ WindowBase base.py  (shared state, session, close)
                                     └─ QMainWindow
```

The import graph follows the same direction and has no cycles: `window.py` imports
`commands.py`, which imports `documents.py`, and so on down to `base.py`.

The real MRO is exactly that list in order:

```
MainWindow > CommandsMixin > DocumentsMixin > NavigationMixin > BookmarksMixin
           > FindMixin > ThemeMixin > WindowBase > QMainWindow
```

### 4.2 Who calls whom

Because each layer sits above the previous ones, a layer may call anything below it.
The actual cross-layer calls in the code are:

| Layer | Calls into |
|---|---|
| `CommandsMixin` | `create_open_action`, `close_current_tab`, `show_tab_search` (documents) · `show_find_bar` (find) · `toggle_bookmark` (bookmarks) · `focus_page_input`, `zoom_in/out`, `reset_zoom`, `next_page`, `previous_page` (navigation) · `set_dark_mode` (theme) · `quit_application` (base) |
| `DocumentsMixin` | `connect_viewer`, `update_page_controls`, `current_viewer` (navigation) · `find_bar`/`find_input`/`find_status` (find) · `save_session` (base) |
| `ThemeMixin` | `save_session` (base) |
| `FindMixin`, `NavigationMixin`, `BookmarksMixin` | only shared state from `base` |

So `CommandsMixin` is the only layer that touches most features — which is exactly
what a menu bar does, and why it sits at the top.

### 4.3 What stayed central

Three things deliberately did **not** get split out:

- **The tab widget itself** (`self.tabs`) is created by `MainWindow.__init__` and
  declared on `WindowBase`. Every layer reads it; none owns it.
- **Cross-feature wiring** (`tabCloseRequested` → `close_tab`, `currentChanged` →
  `refresh_tab_window` + `update_page_controls`, `TabOverflowButton.document_selected`
  → `focus_tab`) is still in `MainWindow.__init__`. Adding a feature still means
  editing both the new file and `window.py`.
- **`save_session()`** stays a real method on `WindowBase`, not a stub, because
  theme, documents, and `closeEvent` all call it.

---

## 5. Why it is a chain (the Pylance reason)

**Python does not require the chain.** At runtime, `self.connect_viewer(...)` inside
`DocumentsMixin.add_pdf` is an ordinary attribute lookup on the instance. As long as
the final `MainWindow` object has that method — which it does, because
`MainWindow` inherits from both mixins — the call works no matter how the classes
are arranged. A flat mixin package would run identically.

**Pylance is why the chain exists.** Pyright type-checks each class against its own
declared bases. For a flat `class DocumentsMixin:` (or `class DocumentsMixin(WindowBase)`)
it sees no `connect_viewer`, no `current_viewer`, no `update_page_controls`, and reports
`reportAttributeAccessIssue` on every cross-mixin call. That is not a false positive:
viewed in isolation, the class genuinely does not satisfy its own body.

There were only three ways to answer that:

1. **Make the layers inherit each other** (chosen). A later layer sees every earlier
   layer's methods, so the calls resolve with no stubs and no suppressions.
2. **Declare the host contract in one shared base** (deferred). Flat mixins plus a
   contract class listing the attributes and method signatures a layer may assume.
   Each mixin stays independent and independently checkable, at the cost of a
   hand-maintained contract file. This is the plan in
   `logs/flat_mixins_declared_contract_refactor.md`.
3. **Suppress the errors** (`# type: ignore`, `getattr(self, "connect_viewer")`).
   Rejected: it removes the checking without replacing it, so a typo like
   `self.connect_viewer` vs `self.connnect_viewer` becomes a runtime crash.

The trade-off the chain buys:

- **Gained:** every cross-layer call is verified by the type checker; the workspace
  reports zero Pylance errors; no stub list to maintain; `super()` stays cooperative
  because no mixin defines `__init__`.
- **Paid:** the inheritance reads as *is-a* when it means *has the layers before it*;
  layer order is load-bearing (a method added to an early layer cannot call a later
  one); each mixin is a `QMainWindow` subclass that is technically instantiable but
  meaningless alone.

Each layer's docstring now names its position ("Layer 5 of the window mixin chain")
so the ordering is visible from any file, and the section above this one is the map.

---

## 6. What else changed (forced by the move)

These are the only behavioural or code edits beyond cutting and pasting:

1. **`repository_root`** became `Path(__file__).resolve().parents[3]`. The old
   `parents[1]` counted from `app/main.py`; `app/ui/main_window/window.py` sits two
   directories deeper. This path is what the bundled `alices-adventures-in-wonderland.pdf`
   and `frankenstein.pdf` fallback resolves against, so an off-by-one here means an
   empty window with no exception.
2. **`go_to_page()`, `zoom_in()`, `zoom_out()`, `reset_zoom()`, `close_current_tab()`**
   now call `current_viewer()` instead of repeating
   `viewer = self.tabs.currentWidget(); if not isinstance(viewer, PDFViewerWidget): return`.
   Same behaviour, one definition of "which document is active".
3. **`quit_application()`** moved to `WindowBase`, next to `closeEvent()`: it is window
   lifecycle, not a command.
4. **`create_shortcuts()`** was kept with the find bar rather than moved to the menu
   code, because it registers exactly one shortcut (`Esc` → `hide_find_bar`). Every
   other shortcut is a menu `QAction`, which is what lets the command palette
   enumerate them.

---

## 7. How it was verified

`AGENTS.md` forbids a test suite, so verification was a throwaway offscreen script
(`QT_QPA_PLATFORM=offscreen`, plus a temporary `XDG_CONFIG_HOME` so the real
`session.json` was never touched). It asserted:

- The MRO is exactly the chain above, in order.
- With no session, both bundled PDFs load (Alice 111 pages, Frankenstein 277) and
  the tab strip is visible.
- All twelve shared attributes exist (`tabs`, `find_bar`, `find_input`, `find_status`,
  `escape_shortcut`, `bottom_bar`, `page_input`, `page_status`, `overflow_button`,
  `dark_mode_action`, `palette_action`, `session_manager`).
- `collect_commands()` returns 13 entries: the 12 menu actions minus the palette
  itself plus `Next Page` / `Previous Page`; `Open`, `Close Tab`, and `Tab Search`
  are present and `Command Palette` is not.
- `tab_entries()` reports `page 1 of 111` hints and one active entry; `tab_commands()`
  returns two rows.
- The page bar follows `next_page()` / `previous_page()`; zoom in exceeds 1.0 and
  `reset_zoom()` returns to exactly 1.0.
- The find bar shows and hides; `toggle_bookmark()` adds then removes page 1.
- `set_dark_mode(False/True)` reaches the stylesheet (`#2E3440` present) and every
  viewer's `dark_mode` flag.
- Closing a tab hides the tab strip again; `focus_tab(0)` works.
- `save_session()` writes inside the temporary XDG directory.

Separately, `python -m app.main` under the offscreen platform starts and stays in its
event loop (killed by `timeout`, exit 124, no traceback), and
`get_errors` over `app/` reports no problems.

---

## 8. Follow-ups

- `find_next()` and `hide_find_bar()` still call `self.tabs.currentWidget()` directly
  while `toggle_bookmark()` uses `current_viewer()`. Finish that cleanup.
- `window.py` contains one method. Splitting `__init__` into `_build_tabs()`,
  `_restore_session()`, `_apply_startup_theme()` would make the startup order
  readable at a glance.
- The planned flat-mixins refactor is written up in
  `logs/flat_mixins_declared_contract_refactor.md`.

---

## 9. Reading list

### Mixins, multiple inheritance, and the MRO

- **Python tutorial — Multiple Inheritance**
  <https://docs.python.org/3/tutorial/classes.html#multiple-inheritance>
  The short, official statement of how `class C(A, B)` resolves attributes and why
  `super()` follows the MRO rather than the parent class.
- **The Python 2.3 Method Resolution Order — Michele Simionato**
  <https://www.python.org/download/releases/2.3/mro/>
  The canonical explanation of C3 linearization, still the reference for *why* the
  MRO of a diamond comes out in a particular order. Read this if the chain above ever
  needs a second parent.
- **Real Python — Inheritance and Composition: A Python OOP Guide**
  <https://realpython.com/inheritance-composition-python/>
  Long but directly on point: it walks through multiple inheritance, the diamond
  problem, and has a dedicated *"Mixing Features With Mixin Classes"* section. Its
  guidance ("use composition to model *has-a*") is precisely the critique of the
  chain that the Option B plan responds to.
- **Real Python — Supercharge Your Classes With Python `super()`**
  <https://realpython.com/python-super/>
  Cooperative `super()` is what makes the chain's `__init__` resolution work. This
  explains why no mixin may define `__init__` in the current design.
- **Django — Using mixins with class-based views**
  <https://docs.djangoproject.com/en/stable/topics/class-based-views/mixins/>
  A large, real-world mixin composition. Most valuable for its explicit warning:
  *"Not all mixins can be used together… you'll have to consider interactions between
  attributes and methods that overlap between the different classes"* — the exact
  hazard of flat mixins discussed in Option B.

### Type checking and contracts

- **PEP 544 — Protocols: Structural subtyping (static duck typing)**
  <https://peps.python.org/pep-0544/>
  Defines `Protocol` and explains nominal vs structural subtyping. This is the
  specification behind the "declare the contract" idea.
- **mypy documentation — Protocols and structural subtyping**
  <https://mypy.readthedocs.io/en/stable/protocols.html>
  The practical companion. Its "Defining subprotocols and subclassing protocols"
  section answers the Option B question directly: explicitly subclassing a protocol
  "forces mypy to verify that your class implementation is actually compatible", and
  omitting an attribute value or method body makes the subclass abstract.
- **Python typing specification**
  <https://typing.readthedocs.io/en/latest/>
  The normative description of what type checkers must do, including the protocol
  chapter. Use it when Pyright and mypy disagree.
- **Python docs — `typing.Protocol`** and **`abc`**
  <https://docs.python.org/3/library/typing.html#typing.Protocol> ·
  <https://docs.python.org/3/library/abc.html>
  For the two enforcement options in Option B: protocol members (structure only,
  no runtime check) versus `@abstractmethod` (checked at instantiation).
- **Pyright documentation**
  <https://github.com/microsoft/pyright/tree/main/docs>
  `type-concepts.md` explains the narrowing rules a contract depends on;
  `configuration.md` lists the diagnostic names such as `reportAttributeAccessIssue`,
  which is the exact error an undeclared cross-mixin call produces.
- **Pylance on the VS Code Marketplace**
  <https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance>
  Confirms what Pylance actually is: Pyright plus editor features (completion, hover,
  go-to-definition, rename). Useful to keep in mind that its complaints are static
  analysis and never affect runtime.

### Qt specifics

- **Qt for Python (PySide6) documentation**
  <https://doc.qt.io/qtforpython-6/>
  Reference for `QMainWindow.menuBar()`, `statusBar()`, toolbars, and shortcuts.
- **Qt — Signals & Slots**
  <https://doc.qt.io/qt-6/signalsandslots.html>
  The mechanism behind `page_changed`, `zoom_changed`, `tabCloseRequested`, and
  `document_selected` — the connections `MainWindow.__init__` still owns.
