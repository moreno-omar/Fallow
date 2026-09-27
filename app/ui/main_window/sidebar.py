"""The toggleable sidebar and the splitter that holds it.

The window's central area is a horizontal ``QSplitter`` with the sidebar on the
left and the document tabs on the right, so a reader can size the sidebar column
to taste and hide it entirely when the page needs the whole window. The sidebar
itself is a :class:`~app.ui.sidebar.Sidebar`, a tab widget holding the bookmarks
pane and the notes pane.

Three details are worth knowing before reading the code:

* ``sidebar_visible`` is the *logical* toggle state. ``QWidget.isVisible()`` is
  ``False`` for every child widget until the window has been shown, so it cannot
  answer "should the toggle be checked?" during ``__init__``.
* the pane width is only *defaulted* on a first run. Once a ``QSettings`` state
  exists the saved layout wins, and nothing recomputes it from the window size.
* the sidebar *contents* are refreshed from the active document and never built
  here. :meth:`refresh_sidebar` is the single place that reads the outline, the
  marks, and the notes, and it reuses its per-book outline cache whenever the
  active document has not changed.
"""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QSplitter

from app.ui.bookmarks_panel import OutlineEntry
from app.ui.main_window.documents import DocumentsMixin
from app.ui.sidebar import BOOKMARKS_TAB, NOTES_TAB, Sidebar
from app.ui.viewer_tab import PDFViewerWidget


class SidebarMixin(DocumentsMixin):
    """Sidebar container, splitter layout, contents, and the panel toggle.

    Layer 7 of the window mixin chain (after ``DocumentsMixin``), so the menu
    layer above it can wire the toggle action and the command palette can find
    it.
    """

    # Pane geometry. Pixels unless the name says otherwise.
    SIDEBAR_MIN_WIDTH = 320
    PDF_MIN_WIDTH = 400
    SIDEBAR_DEFAULT_RATIO = 0.30
    SIDEBAR_DEFAULT_MIN = 360
    SIDEBAR_DEFAULT_MAX = 640
    SIDEBAR_AUTO_HIDE_RATIO = 0.10
    SIDEBAR_NARROW_WINDOW = 900
    SIDEBAR_AUTO_HIDE_DELAY_MS = 200

    sidebar_splitter: QSplitter
    sidebar: Sidebar
    sidebar_visible: bool
    # Created by ``CommandsMixin.create_sidebar_action``, which runs after this
    # layer, so it starts as ``None``: the splitter exists before the menu that
    # offers the toggle does.
    sidebar_action: QAction | None = None
    # Book id -> outline rows. Keyed by book rather than by tab, because
    # content-hash identity means two tabs showing the same bytes have the same
    # table of contents; the cache is dropped when the library is switched,
    # since book ids belong to one database.
    _outline_cache: dict[int, list[OutlineEntry]]

    def create_sidebar(self) -> None:
        """Build the sidebar splitter and restore the layout it had last run."""
        self.sidebar = Sidebar()
        self.sidebar.setMinimumWidth(self.SIDEBAR_MIN_WIDTH)
        self.sidebar.bookmarks_panel.page_requested.connect(self.navigate_to_page)
        self.sidebar.bookmarks_panel.mark_removed.connect(self.remove_bookmark)
        self.sidebar.notes_panel.note_requested.connect(self.open_note)
        self.sidebar.notes_panel.note_created.connect(self.create_note)
        self.sidebar.notes_panel.note_edited.connect(self.save_note)
        self.sidebar.currentChanged.connect(self.save_sidebar_tab)
        # The document pane keeps its own floor, so a drag can never squeeze a
        # page below a readable width, and it may not be collapsed away.
        self.tabs.setMinimumWidth(self.PDF_MIN_WIDTH)

        self.sidebar_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.sidebar_splitter.addWidget(self.sidebar)
        self.sidebar_splitter.addWidget(self.tabs)
        self.sidebar_splitter.setCollapsible(1, False)
        self.sidebar_splitter.splitterMoved.connect(self.sidebar_splitter_moved)
        self.setCentralWidget(self.sidebar_splitter)

        self._sidebar_auto_hide_timer = QTimer(self)
        self._sidebar_auto_hide_timer.setSingleShot(True)
        self._sidebar_auto_hide_timer.setInterval(self.SIDEBAR_AUTO_HIDE_DELAY_MS)
        self._sidebar_auto_hide_timer.timeout.connect(self.finish_sidebar_drag)

        self._last_sidebar_width = self.SIDEBAR_DEFAULT_MIN
        self._dragged_sidebar_width = self.SIDEBAR_DEFAULT_MIN
        self._sidebar_drag_pending = False
        self._sidebar_first_run = False
        self._outline_cache = {}

        if self.restore_sidebar_settings():
            # No stored layout. The window is maximized right after this, and the
            # first resize is what reveals the width the splitter ends up with,
            # so the 30% default is applied from there instead of from a
            # not-yet-sized widget.
            self._sidebar_first_run = True
            self.sidebar_visible = True

        self.tabs.currentChanged.connect(self.refresh_sidebar)
        self.sidebar.setVisible(self.sidebar_visible)
        self.refresh_sidebar()

    # -- persistence ---------------------------------------------------------------

    def read_sidebar_setting(self, name: str) -> object | None:
        """Read a sidebar setting, falling back to the Phase 12 ``notes/`` key.

        Phase 12 stored its layout under ``notes/``. Reading that key once means
        an existing layout carries over instead of snapping back to the default.
        """
        for key in (f"sidebar/{name}", f"notes/{name}"):
            value = self.settings.value(key)
            if value is not None:
                return value
        return None

    def restore_sidebar_settings(self) -> bool:
        """Restore the saved sidebar layout, reporting whether this is a first run."""
        stored_state = self.read_sidebar_setting("splitter_state")
        if stored_state is None or not self.sidebar_splitter.restoreState(stored_state):
            return True
        stored_width = self.setting_int(self.read_sidebar_setting("width"), self.SIDEBAR_DEFAULT_MIN)
        self._last_sidebar_width = max(stored_width, self.SIDEBAR_MIN_WIDTH)
        self.sidebar_visible = self.setting_bool(self.read_sidebar_setting("visible"), True)
        stored_tab = self.read_sidebar_setting("tab")
        if isinstance(stored_tab, str):
            self.sidebar.set_active_tab(stored_tab)
        return False

    def save_sidebar_settings(self) -> None:
        """Store the splitter state, the toggle state, the tab, and the pane width."""
        self.settings.setValue("sidebar/splitter_state", self.sidebar_splitter.saveState())
        self.settings.setValue("sidebar/visible", self.sidebar_visible)
        self.settings.setValue("sidebar/width", self._last_sidebar_width)
        self.save_sidebar_tab()

    def save_sidebar_tab(self, _index: int = -1) -> None:
        """Remember which sidebar tab the reader is on."""
        self.settings.setValue("sidebar/tab", self.sidebar.active_tab_name())

    # -- contents ------------------------------------------------------------------

    def refresh_sidebar(self, _index: int = -1) -> None:
        """Point the sidebar at the active document, or empty it when none is open.

        A pending note edit is flushed first, so switching documents can never
        discard what was just typed into the note being left behind.
        """
        self.sidebar.notes_panel.flush_editor()
        viewer = self.current_viewer()
        if viewer is None:
            self.sidebar.bookmarks_panel.clear()
            self.sidebar.notes_panel.clear()
            return
        book_id = self.book_id_for_viewer(viewer)
        self.sidebar.bookmarks_panel.set_outline(self.outline_for_book(book_id, viewer))
        self.sidebar.bookmarks_panel.set_marks(self.database.bookmarks(book_id))
        self.reload_notes(book_id)

    def outline_for_book(self, book_id: int, viewer: PDFViewerWidget) -> list[OutlineEntry]:
        """Return a document's outline, asking PyMuPDF for it at most once per book.

        The cache is keyed by *book*, not by tab: content-hash identity means two
        tabs showing the same bytes have the same table of contents, so moving
        between documents stays free after the first visit to each.
        """
        cached = self._outline_cache.get(book_id)
        if cached is None:
            cached = viewer.engine.outline()
            self._outline_cache[book_id] = cached
        return cached

    def show_sidebar_tab(self, tab_name: str) -> None:
        """Show the sidebar on one of its tabs and hand the keyboard to that pane."""
        if not self.sidebar_visible:
            self.set_sidebar_visible(True)
        self.sidebar.set_active_tab(tab_name)
        self.sidebar.focus_active_panel()

    def navigate_to_page(self, page: int) -> None:
        """Jump the active document to a zero-based page chosen in the sidebar."""
        viewer = self.current_viewer()
        if viewer is None:
            return
        viewer.set_page(page)
        viewer.focus_canvas()

    def remove_bookmark(self, page: int) -> None:
        """Delete the active document's mark on ``page`` and refresh the list."""
        viewer = self.current_viewer()
        if viewer is None:
            return
        self.database.remove_bookmark(self.book_id_for_viewer(viewer), page)
        self.refresh_sidebar()
        self.statusBar().showMessage(f"Bookmark removed from page {page + 1}", self.STATUS_TIMEOUT_MS)

    def toggle_bookmark(self) -> None:
        """Toggle the active page's mark, then refresh the list it appears in.

        The write itself belongs to :class:`~app.ui.main_window.bookmarks.BookmarksMixin`,
        one layer below this one; the panel that has to show the result is owned
        here, so the refresh is added on this layer through a cooperative
        ``super()`` call.
        """
        super().toggle_bookmark()
        self.refresh_sidebar()

    # -- notes ---------------------------------------------------------------------

    def create_note(self) -> None:
        """Create a note for the active document and open it for typing."""
        viewer = self.current_viewer()
        if viewer is None:
            self.statusBar().showMessage("Open a document before creating a note", self.STATUS_TIMEOUT_MS)
            return
        self.sidebar.notes_panel.flush_editor()
        book_id = self.book_id_for_viewer(viewer)
        note = self.database.create_note(book_id, page=viewer.current_page)
        self.reload_notes(book_id, note_to_open=note.id)
        self.show_sidebar_tab(NOTES_TAB)
        self.statusBar().showMessage(f"New note for page {viewer.current_page + 1}", self.STATUS_TIMEOUT_MS)

    def reload_notes(self, book_id: int, note_to_open: int | None = None) -> None:
        """Refresh the notes list and keep a sensible note in the editor.

        The editor is only reloaded when it has to change, so a refresh caused by
        something else (a bookmark toggle, say) cannot reset the cursor position
        of the note being typed into.
        """
        notes = self.database.notes_for_book(book_id)
        self.sidebar.notes_panel.set_notes(notes)
        note_ids = {note.id for note in notes}
        target = note_to_open if note_to_open in note_ids else self.sidebar.notes_panel.current_note_id()
        if target not in note_ids:
            target = notes[0].id if notes else None
        if target is None:
            self.sidebar.notes_panel.close_note()
        elif target != self.sidebar.notes_panel.current_note_id():
            self.open_note(target)

    def open_note(self, note_id: int) -> None:
        """Load a note's Markdown into the editor.

        A row whose file has gone missing opens an empty editor rather than
        failing; the next keystroke writes the file again.
        """
        note = self.database.note(note_id)
        if note is None:
            return
        body = self.database.read_note_body(note_id)
        self.sidebar.notes_panel.show_note(note, body or "")

    def save_note(self, note_id: int, body: str) -> None:
        """Persist an edited note and refresh its label in the list."""
        note = self.database.update_note_body(note_id, body)
        if note is not None:
            self.sidebar.notes_panel.update_note(note)

    # -- layout --------------------------------------------------------------------

    def reference_window_width(self) -> int:
        """Return the width the splitter occupies, in pixels.

        The window is shown maximized, so the screen's available width is the
        width the splitter ends up with even on the first resize event, before
        the window manager has delivered the maximize resize.
        """
        screen = self.screen() or QGuiApplication.primaryScreen()
        screen_width = screen.availableGeometry().width() if screen is not None else 0
        return max(self.sidebar_splitter.width(), screen_width, self.width())

    def apply_default_sidebar_layout(self, window_width: int) -> None:
        """Size the sidebar for a first run, or collapse it on a narrow window."""
        width = self.default_sidebar_width(window_width)
        if width == 0:
            # Too little room for a page and a sidebar column side by side.
            self.set_sidebar_visible(False)
            return
        self.sidebar_visible = True
        self.sidebar.setVisible(True)
        self.apply_sidebar_width(width)
        # ``set_sidebar_visible`` keeps the menu in step; showing the pane directly
        # skips that, so the checkmark has to be corrected here too.
        self.sync_sidebar_action()
        self.save_sidebar_settings()

    def default_sidebar_width(self, window_width: int) -> int:
        """Return the first-run pane width, or ``0`` when the window is too narrow.

        Split out from :meth:`apply_default_sidebar_layout` because this is the
        whole rule (30% of the window, clamped) and it does not need a laid-out
        widget to be checked.
        """
        if window_width < self.SIDEBAR_NARROW_WINDOW:
            return 0
        target = round(window_width * self.SIDEBAR_DEFAULT_RATIO)
        return min(max(target, self.SIDEBAR_DEFAULT_MIN), self.SIDEBAR_DEFAULT_MAX)

    def apply_sidebar_width(self, width: int) -> None:
        """Give the sidebar ``width`` pixels and the document pane the rest.

        The splitter scales the requested sizes when they do not fill it, so the
        span is measured from the widget rather than passed in: a pane width that
        was valid before a resize must not come back as a different number.
        """
        span = self.splitter_span()
        if span <= 0:
            # Not laid out yet; a self-consistent request is scaled on show.
            span = width + self.PDF_MIN_WIDTH
        document_width = max(span - width, self.PDF_MIN_WIDTH)
        self.sidebar_splitter.setSizes([width, document_width])
        self._last_sidebar_width = width

    def splitter_span(self) -> int:
        """Return the pixels the two panes share, excluding the splitter handle.

        ``setSizes`` distributes exactly this much, so asking for pane widths
        that add up to anything else makes Qt scale them -- and a 640px pane
        comes back as 636.
        """
        span = self.sidebar_splitter.width() - self.sidebar_splitter.handleWidth() * (
            self.sidebar_splitter.count() - 1
        )
        return span if span > 0 else 0

    # -- visibility ----------------------------------------------------------------

    def set_sidebar_visible(self, visible: bool) -> None:
        """Show or hide the sidebar pane, keeping its width for the next toggle."""
        self.sidebar_visible = visible
        if visible:
            self.sidebar.setVisible(True)
            self.apply_sidebar_width(self._last_sidebar_width)
        else:
            sizes = self.sidebar_splitter.sizes()
            dragged = sizes[0] if len(sizes) == 2 else 0
            if dragged >= self.SIDEBAR_MIN_WIDTH:
                self._last_sidebar_width = dragged
            self.sidebar.setVisible(False)
        self.sync_sidebar_action()
        self.save_sidebar_settings()

    def sync_sidebar_action(self) -> None:
        """Keep the menu toggle in step with the panel.

        The drag-driven auto-hide hides the panel without going through the
        action, so the checkmark has to be corrected from here. Signals are
        blocked because the action's own ``toggled`` is what calls back in.
        """
        if self.sidebar_action is None or self.sidebar_action.isChecked() == self.sidebar_visible:
            return
        self.sidebar_action.blockSignals(True)
        self.sidebar_action.setChecked(self.sidebar_visible)
        self.sidebar_action.blockSignals(False)

    # -- drag handling -------------------------------------------------------------

    def sidebar_splitter_moved(self, position: int, index: int) -> None:
        """Record a drag and arm the debounce that decides what to do with it."""
        del index  # Only the horizontal handle's position matters here.
        self._dragged_sidebar_width = position
        self._sidebar_drag_pending = True
        # Wait for the drag to finish: hiding the pane while the handle is still
        # under the mouse fights the drag it is reacting to.
        self._sidebar_auto_hide_timer.start()

    def finish_sidebar_drag(self) -> None:
        """Hide the pane when a drag left it below the auto-hide threshold."""
        if not self._sidebar_drag_pending:
            return
        self._sidebar_drag_pending = False
        if self._dragged_sidebar_width < self.auto_hide_width():
            self.set_sidebar_visible(False)
            return
        # Remember only usable widths, so a collapse can never become the size
        # the next toggle restores.
        self._last_sidebar_width = self._dragged_sidebar_width
        self.save_sidebar_settings()

    def auto_hide_width(self) -> int:
        """Return the pane width, in pixels, below which the panel hides itself."""
        return max(int(self.sidebar_splitter.width() * self.SIDEBAR_AUTO_HIDE_RATIO), 1)

    # -- lifecycle -----------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        """Apply the first-run 30% default once the splitter has a real width."""
        super().resizeEvent(event)
        if self._sidebar_first_run and self.sidebar_splitter.width() > 0:
            self._sidebar_first_run = False
            self.apply_default_sidebar_layout(self.reference_window_width())

    def switch_library(self, data_root: Path | None) -> None:
        """Switch the library, then repoint the sidebar at the new contents."""
        super().switch_library(data_root)
        # Book ids belong to one database, so a cached outline from the previous
        # library would be attached to the wrong book.
        self._outline_cache.clear()
        self.refresh_sidebar()

    def closeEvent(self, event) -> None:
        """Save a pending note edit and the sidebar layout before the window closes."""
        self.sidebar.notes_panel.flush_editor()
        self.save_sidebar_settings()
        super().closeEvent(event)
