# Plan (postponed) — flat mixins with a declared host contract (Option B)

**Drafted:** 2026-09-25
**Status:** NOT IMPLEMENTED. Plan only. The shipped code is the layered chain described in
`logs/26-9-25_refactor.md`; nothing in this document exists in the repository yet.
**Estimated size:** ~6 import lines, 6 class declarations, 6 docstring paragraphs, 1 new small
method, 1 new file. No method body changes.

---

## 1. Goal

Keep the feature split (`theme`, `find`, `bookmarks`, `navigation`, `documents`, `commands`), but
make each mixin **flat and independently checkable** instead of inheriting the layer below it.

Two problems with the current chain motivate this:

1. **The inheritance is dishonest.** `DocumentsMixin(NavigationMixin)` reads as "a documents mixin
   *is a* navigation mixin", which is false. It only means "may call navigation's methods".
2. **A mixin cannot be examined alone.** To type-check or reason about `FindMixin`, you must follow
   the chain down to `WindowBase` and `QMainWindow`. A mixin is also not reusable on any host other
   than the one class it was chained into.

What we keep from the chain: **zero Pylance errors with no stubs, no `# type: ignore`, and no
suppressions.** Option B keeps that property by making the contract explicit instead of implied by
class order.

---

## 2. What "independent" has to mean here

Pylance type-checks a class against its declared bases. A flat mixin that calls
`self.connect_viewer(...)` gets `reportAttributeAccessIssue`, and that is a *correct* diagnosis:
viewed alone, the class does not satisfy its own body. "Independence" therefore cannot mean
"ignore the errors" — it means **declare the host contract in one place that every mixin inherits**.

After this refactor:

- `Pylance` resolves every cross-mixin call through the contract, so the workspace stays error-free.
- Each mixin imports only the contract (plus third-party libraries and its own helpers) — **no
  sibling mixin imports at all**.
- Each mixin can be type-checked on its own, and can be exercised against a *fake host* (a
  `WindowContract` subclass with trivial implementations) instead of a fully built `MainWindow`.
- The cost, stated plainly: the contract is hand-maintained, and a member that a layer forgets to
  implement fails at **runtime**, not at type-check time. This is the exact property the chain gave
  away for free — the plan below adds a guard test for it (step 6).

---

## 3. Target shape

```
WindowBase(QMainWindow)                     base.py      state + session + close (real code)
  └─ WindowContract(WindowBase)             contract.py  interface a feature layer may assume
       ├─ ThemeMixin(WindowContract)        theme.py
       ├─ FindMixin(WindowContract)         find.py
       ├─ BookmarksMixin(WindowContract)    bookmarks.py
       ├─ NavigationMixin(WindowContract)   navigation.py
       ├─ DocumentsMixin(WindowContract)    documents.py
       └─ CommandsMixin(WindowContract)     commands.py

MainWindow(ThemeMixin, FindMixin, BookmarksMixin,
           NavigationMixin, DocumentsMixin, CommandsMixin)   window.py
```

`base.py` keeps real behaviour. `contract.py` is almost entirely type signatures — it is the
documented answer to "what may a feature layer assume about the window?".

The base list in `MainWindow` mirrors today's dependency order purely for readability. With sibling
mixins, order now decides only one thing: **if two mixins define the same name, the one listed
earlier silently wins.** That hazard replaces the chain's ordering rule and needs a convention
(section 7).

Expected MRO:

```
MainWindow > ThemeMixin > FindMixin > BookmarksMixin > NavigationMixin
           > DocumentsMixin > CommandsMixin > WindowContract > WindowBase > QMainWindow
```

`MainWindow.__init__` still calls `super().__init__()`, which walks past the mixins (none defines
`__init__`) to `QMainWindow.__init__`. `closeEvent` stays on `WindowBase`, whose `super()` is
`QMainWindow` in this MRO, so the override still reaches Qt.

---

## 4. The contract, member by member

### 4.1 Already real on `WindowBase` (no change)

| Member | Kind |
|---|---|
| `STATUS_TIMEOUT_MS = 3000` | constant |
| `session_manager`, `tabs`, `overflow_button`, `dark_mode`, `dark_mode_action`, `palette_action` | attribute declarations |
| `save_session() -> None` | real method (called by theme, documents, `closeEvent`) |
| `quit_application() -> None` | real method (called by the `File > Quit` action) |
| `closeEvent(event)` | real method (Qt override) |

### 4.2 New: 16 stub signatures on `WindowContract`

These are exactly the members one layer calls on another. Anything only ever called by
`MainWindow.__init__` (such as `create_menu_bar()`, `create_bottom_bar()`, `create_find_bar()`,
`create_shortcuts()`, `add_pdf()`) does **not** need a stub, because `MainWindow` sees the real
implementations.

| Member | Provided by | Called from |
|---|---|---|
| `connect_viewer(viewer: PDFViewerWidget) -> None` | navigation | documents (`add_pdf`) |
| `update_page_controls(tab_index: int) -> None` | navigation | documents (`add_pdf`) |
| `current_viewer() -> PDFViewerWidget \| None` | navigation | documents (`close_current_tab`, `focus_tab`) |
| `focus_page_input() -> None` | navigation | commands (menu) |
| `next_page() -> None` | navigation | commands (`viewer_commands`) |
| `previous_page() -> None` | navigation | commands (`viewer_commands`) |
| `zoom_in() -> None` | navigation | commands (menu) |
| `zoom_out() -> None` | navigation | commands (menu) |
| `reset_zoom() -> None` | navigation | commands (menu) |
| `toggle_bookmark() -> None` | bookmarks | commands (menu) |
| `show_find_bar() -> None` | find | commands (menu) |
| `reset_find_bar() -> None` | find | documents (`close_tab`) — **new method, see 4.3** |
| `create_open_action() -> QAction` | documents | commands (`create_menu_bar`) |
| `close_current_tab() -> None` | documents | commands (menu) |
| `show_tab_search() -> None` | documents | commands (menu) |
| `set_dark_mode(enabled: bool) -> None` | theme | commands (`dark_mode_action.toggled`) |

Sixteen stubs is the whole interface. If the number grows much beyond that, the split is wrong and
the real fix is composition, not a bigger contract.

### 4.3 One small design improvement to make first

`DocumentsMixin.close_tab()` currently reaches into find's widgets directly:

```
self.find_bar.setVisible(False)
self.find_input.clear()
self.find_status.clear()
```

That would force three *attributes* into the contract. Instead add a `FindMixin.reset_find_bar()`
method holding those three lines, and have `close_tab()` call it. The contract then exposes
behaviour rather than widget internals, and find's widgets stay private to `find.py`. Do this step
**before** the flat conversion, while the chain still makes it a one-line change.

### 4.4 Keeping the guard honest

Alongside the stubs, keep an explicit list of contract member names in `contract.py`, e.g.
`CONTRACT_MEMBERS: tuple[str, ...]`. It costs one line per member and makes the guard test in
step 6 trivial and explicit — no introspection of function bodies.

---

## 5. Steps

Each step ends with the same verification, so a regression is always attributable to one change:
`get_errors` over `app/` returns nothing, and the offscreen smoke script passes.

1. **Baseline.** Recreate the offscreen smoke script described in
   `logs/26-9-25_refactor.md` section 7 (it is not committed) and save its output. It is the only
   regression net this project has.
2. **Extract `reset_find_bar()`.** Add it to `FindMixin`; call it from `DocumentsMixin.close_tab()`.
   Verify.
3. **Add `contract.py`.** `class WindowContract(WindowBase)` with the 16 stubs, `CONTRACT_MEMBERS`,
   and a module docstring explaining the rule in section 7. Nothing inherits it yet. Verify
   (no change expected).
4. **Flatten the mixins, one file at a time.** For each of the six: change the base class to
   `WindowContract`, replace the sibling import with a contract import, delete the
   "Layer N of the window mixin chain" docstring line, and rewrite the sentence that describes the
   connection. Verify after each file rather than all six at once — that is how you find out which
   one broke the MRO.
5. **Change `MainWindow`'s base list** from `(CommandsMixin)` to the explicit six-base tuple, and
   update `window.py`'s docstring: the numbered layer list becomes a note that the order is for
   readability and decides name conflicts. Verify.
6. **Add the guard** (a throwaway script, or a small check in the smoke script): for every name in
   `CONTRACT_MEMBERS`, assert
   `getattr(MainWindow, name) is not getattr(WindowContract, name)` — i.e. a mixin really overrides
   the stub rather than the stub being reached at runtime.
7. **Add the disjointness check**: no name should be defined by two mixin modules. Introspect the
   six modules and report duplicates; a duplicate means a silently shadowed implementation.
8. **Update `SUMMARY.md`** with the new shape, and update `/memories/repo/fallow-gui-notes.md` so the
   chain description becomes historical.
9. **Optional — enforce instead of document.** Promote the 16 stubs to `@abstractmethod`. `ABCMeta`
   computes abstractness from the resolved MRO, so `MainWindow` stays instantiable as long as each
   mixin provides a concrete override; if one does not, startup fails loudly with
   `TypeError: Can't instantiate abstract class`. That turns the guard test into a language
   guarantee. Verify by temporarily deleting one override and confirming the failure, then restoring
   it.
10. **Optional, only if a mixin must ever run on a non-`QMainWindow` host.** Move the remaining Qt
    window API used inside mixins (`statusBar()`, `menuBar()`) behind contract methods. Today three
    mixins call `self.statusBar()` and `CommandsMixin` calls `self.menuBar()`, which is what keeps
    `WindowBase` pinned to `QMainWindow`.

### Deliberately out of scope

Composition (`FindBar(QToolBar)`, `PageBar(QToolBar)`, `ThemeController`) is the stricter fix and
the only one that makes these units independently *constructible*. It is a different, larger
refactor: `MainWindow` would wire signals instead of calling methods. Option B is the cheap step
that buys honest inheritance and a test seam without touching behaviour.

---

## 6. Acceptance criteria

- `get_errors` over `app/` is empty, with no `# type: ignore` and no stub bodies reached at runtime.
- The smoke script passes with the same results as the baseline, differing only in the printed MRO.
- `MainWindow.__mro__` equals the expected flat order in section 3.
- Every name in `CONTRACT_MEMBERS` is overridden in `MainWindow`.
- No mixin module imports another mixin module (checkable with a search for
  `from app.ui.main_window.` in each file — the only allowed target is `contract`/`base`).
- No method body in the six mixin files changed. `git diff` should show imports, class headers, and
  docstrings only.

---

## 7. Rules to adopt with the new shape

Flat mixins need conventions the chain enforced automatically. Write these into the module docs
(and ideally `AGENTS.md`):

1. **One owner per name.** A method or attribute belongs to exactly one mixin. Duplicates are
   silently resolved by `MainWindow`'s base order, so the disjointness check in step 7 replaces the
   chain's ordering safety.
2. **The contract only grows when a second layer needs something.** Adding a stub the moment a
   method exists re-creates the monolithic class one signature at a time.
3. **The contract describes behaviour, not widgets.** Prefer `reset_find_bar()` over exposing
   `find_input` — see 4.3.
4. **A stub in `WindowContract` is a promise.** If a mixin removes an implementation, the guard test
   is what tells you.

---

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| A cross-mixin call is added without a contract entry | Pylance reports `reportAttributeAccessIssue` in the calling mixin — the error *is* the reminder. This is the one failure mode Option B detects automatically. |
| A contract member is never implemented | Guard test (step 6); optionally `@abstractmethod` (step 9). |
| Two mixins define the same name, one silently shadowed | Disjointness check (step 7) plus rule 1. |
| Contract drifts from reality over time | Keep `CONTRACT_MEMBERS` beside the stubs so both are edited together; review it whenever a mixin gains a public method. |
| `ABCMeta` ordering surprises if step 9 is taken | Keep step 9 separate from the flattening; verify by deleting an override on purpose. |
| Mixins remain `QMainWindow` subclasses, so `WindowContract()` can be instantiated and does nothing useful | Documented, not prevented. `WindowBase` could raise in `__init__` when the concrete type is not `MainWindow`, at the cost of a guard clause in a constructible class — not recommended unless it actually bites. |
| Rollback needed | Cheap: revert the six class declarations and the `MainWindow` base list. No method bodies are touched, so the chain remains a valid fallback. |

---

## 9. Decisions to make before starting

1. **Plain stubs (B2) or `@abstractmethod` (B1)?** Recommendation: ship B2 first as one mechanical
   change, then evaluate B1 as an isolated follow-up.
2. **`base.py` + `contract.py`, or one file?** Recommendation: two. `base.py` is real behaviour;
   `contract.py` is an interface, and mixing them invites the contract to absorb logic.
3. **Re-declare the shared attributes on the contract?** Recommendation: no. `WindowBase` already
   declares them; a second declaration is a second thing to keep in sync.
4. **Do mixins ever need a non-`QMainWindow` host?** If no, skip step 10 and keep `WindowBase`
   pinned to Qt. If yes, plan step 10 as its own piece of work.
5. **Where do rules 1–4 live?** `AGENTS.md` makes them binding for future changes; module docstrings
   make them discoverable. Recommendation: a short paragraph in both `contract.py` and `AGENTS.md`.

---

## 10. Reading list

Most relevant first.

- **PEP 544 — Protocols: Structural subtyping (static duck typing)**
  <https://peps.python.org/pep-0544/>
  The specification behind "declare the contract". Explains the nominal vs structural distinction
  that decides whether the contract should be a base class (nominal, what Option B uses) or a
  `Protocol` (structural, what a fake host in tests would use).
- **mypy — Protocols and structural subtyping**
  <https://mypy.readthedocs.io/en/stable/protocols.html>
  The practical half of the same story, and the clearest answer to the Option B question.
  Key passage: explicitly subclassing a protocol "forces mypy to verify that your class
  implementation is actually compatible with the protocol", and leaving out an attribute value or
  method body "will make it implicitly abstract" — i.e. subclassing the contract is exactly how you
  ask a type checker to enforce it. Also covers invariance of attributes, which matters if the
  contract ever declares a mutable field.
- **Python typing specification**
  <https://typing.readthedocs.io/en/latest/>
  The normative rules a checker must follow (including the protocol chapter). Use it when Pyright
  and mypy disagree about a contract detail.
- **Python docs — `typing.Protocol`**
  <https://docs.python.org/3/library/typing.html#typing.Protocol>
  Short reference for what a protocol member may look like and what `runtime_checkable` does and
  does not guarantee.
- **Python docs — `abc`**
  <https://docs.python.org/3/library/abc.html>
  Needed for step 9. Explains `ABCMeta` and `__abstractmethods__`, which is what decides whether
  `MainWindow` is instantiable once stubs become `@abstractmethod`.
- **Pyright documentation — `type-concepts.md`, `configuration.md`**
  <https://github.com/microsoft/pyright/tree/main/docs>
  `type-concepts.md` for the narrowing rules the contract relies on; `configuration.md` for the
  diagnostic names to search for, notably `reportAttributeAccessIssue`, the error an undeclared
  cross-mixin call produces.
- **Pylance on the VS Code Marketplace**
  <https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance>
  Confirms Pylance is Pyright plus editor features: a static analyser, so none of its findings
  affect runtime and none of them can be "worked around" by the interpreter.
- **Real Python — Implementing Interfaces in Python: ABCs and Protocols**
  <https://realpython.com/python-interface/>
  A gentler introduction than PEP 544 if the protocol/ABC distinction is still fuzzy, including when
  each is the right tool.
- **Real Python — Inheritance and Composition: A Python OOP Guide**
  <https://realpython.com/inheritance-composition-python/>
  Useful for the decision *after* Option B. Its composition sections show what the final step away
  from mixins would look like, and its "is-a / has-a" test is a good check on whether the contract
  is hiding a relationship that should be composition.
- **Django — Using mixins with class-based views**
  <https://docs.djangoproject.com/en/stable/topics/class-based-views/mixins/>
  Read it for the failure stories, not the API: "Not all mixins can be used together… you'll have to
  consider interactions between attributes and methods that overlap between the different classes",
  and its advice to fall back to a simpler base rather than combine more. That is rule 2 in
  section 7, from people who learned it the expensive way.
