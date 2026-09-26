"""The toggleable notes panel and the splitter that holds it.

The window's central area is a horizontal ``QSplitter`` with the notes panel on
the left and the document tabs on the right, so a reader can size the notes
column to taste and hide it entirely when the page needs the whole window.

Two details are worth knowing before reading the code:

* ``notes_visible`` is the *logical* toggle state. ``QWidget.isVisible()`` is
  ``False`` for every child widget until the window has been shown, so it cannot
  answer "should the toggle be checked?" during ``__init__``.
* the pane width is only *defaulted* on a first run. Once a ``QSettings`` state
  exists the saved layout wins, and nothing recomputes it from the window size.
"""

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QSplitter

from app.ui.main_window.documents import DocumentsMixin
from app.ui.notes_panel import NotesPanel


class NotesMixin(DocumentsMixin):
    """Notes panel, splitter layout, and the panel toggle shortcut.

    Layer 7 of the window mixin chain (after ``DocumentsMixin``), so the menu
    layer above it can wire the toggle action and the command palette can find
    it.
    """

    # Pane geometry. Pixels unless the name says otherwise.
    NOTES_MIN_WIDTH = 320
    PDF_MIN_WIDTH = 400
    NOTES_DEFAULT_RATIO = 0.30
    NOTES_DEFAULT_MIN = 360
    NOTES_DEFAULT_MAX = 640
    NOTES_AUTO_HIDE_RATIO = 0.10
    NOTES_NARROW_WINDOW = 900
    NOTES_AUTO_HIDE_DELAY_MS = 200

    # Layout is remembered across runs. The organisation matches the directory
    # the session file uses (``$XDG_CONFIG_HOME/linux-pdf-reader``), so the app
    # keeps one config folder instead of two.
    SETTINGS_ORGANIZATION = "linux-pdf-reader"
    SETTINGS_APPLICATION = "Fallow PDF Reader"

    notes_splitter: QSplitter
    notes_panel: NotesPanel
    notes_settings: QSettings
    notes_visible: bool
    # Created by ``CommandsMixin.create_notes_panel_action``, which runs after
    # this layer, so it starts as ``None``: the splitter exists before the menu
    # that offers the toggle does.
    notes_action: QAction | None = None

    def create_notes_panel(self) -> None:
        """Build the notes splitter and restore the layout it had last run."""
        self.notes_settings = QSettings(self.SETTINGS_ORGANIZATION, self.SETTINGS_APPLICATION)
        self.notes_panel = NotesPanel()
        self.notes_panel.setMinimumWidth(self.NOTES_MIN_WIDTH)
        # The document pane keeps its own floor, so a drag can never squeeze a
        # page below a readable width, and it may not be collapsed away.
        self.tabs.setMinimumWidth(self.PDF_MIN_WIDTH)

        self.notes_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.notes_splitter.addWidget(self.notes_panel)
        self.notes_splitter.addWidget(self.tabs)
        self.notes_splitter.setCollapsible(1, False)
        self.notes_splitter.splitterMoved.connect(self.notes_splitter_moved)
        self.setCentralWidget(self.notes_splitter)

        self._notes_auto_hide_timer = QTimer(self)
        self._notes_auto_hide_timer.setSingleShot(True)
        self._notes_auto_hide_timer.setInterval(self.NOTES_AUTO_HIDE_DELAY_MS)
        self._notes_auto_hide_timer.timeout.connect(self.finish_notes_drag)

        self._last_notes_width = self.NOTES_DEFAULT_MIN
        self._dragged_notes_width = self.NOTES_DEFAULT_MIN
        self._notes_drag_pending = False
        self._notes_first_run = False

        if self.restore_notes_settings():
            # No stored layout. The window is maximized right after this, and the
            # first resize is what reveals the width the splitter ends up with,
            # so the 30% default is applied from there instead of from a
            # not-yet-sized widget.
            self._notes_first_run = True
            self.notes_visible = True
        self.notes_panel.setVisible(self.notes_visible)

    # -- persistence ---------------------------------------------------------------

    def restore_notes_settings(self) -> bool:
        """Restore the saved splitter layout, reporting whether this is a first run."""
        stored_state = self.notes_settings.value("notes/splitter_state")
        if stored_state is None or not self.notes_splitter.restoreState(stored_state):
            return True
        stored_width = self.notes_settings.value("notes/width", self.NOTES_DEFAULT_MIN, type=int)
        self._last_notes_width = max(int(stored_width), self.NOTES_MIN_WIDTH)
        stored_visible = self.notes_settings.value("notes/visible", True, type=bool)
        self.notes_visible = bool(stored_visible)
        return False

    def save_notes_settings(self) -> None:
        """Store the splitter state, the toggle state, and the last pane width."""
        self.notes_settings.setValue("notes/splitter_state", self.notes_splitter.saveState())
        self.notes_settings.setValue("notes/visible", self.notes_visible)
        self.notes_settings.setValue("notes/width", self._last_notes_width)

    # -- layout --------------------------------------------------------------------

    def reference_window_width(self) -> int:
        """Return the width the splitter occupies, in pixels.

        The window is shown maximized, so the screen's available width is the
        width the splitter ends up with even on the first resize event, before
        the window manager has delivered the maximize resize.
        """
        screen = self.screen() or QGuiApplication.primaryScreen()
        screen_width = screen.availableGeometry().width() if screen is not None else 0
        return max(self.notes_splitter.width(), screen_width, self.width())

    def apply_default_notes_layout(self, window_width: int) -> None:
        """Size the notes pane for a first run, or collapse it on a narrow window."""
        width = self.default_notes_width(window_width)
        if width == 0:
            # Too little room for a page and a notes column side by side.
            self.set_notes_panel_visible(False)
            return
        self.notes_visible = True
        self.notes_panel.setVisible(True)
        self.apply_notes_width(width)
        self.save_notes_settings()

    def default_notes_width(self, window_width: int) -> int:
        """Return the first-run pane width, or ``0`` when the window is too narrow.

        Split out from :meth:`apply_default_notes_layout` because this is the
        whole rule (30% of the window, clamped) and it does not need a laid-out
        widget to be checked.
        """
        if window_width < self.NOTES_NARROW_WINDOW:
            return 0
        target = round(window_width * self.NOTES_DEFAULT_RATIO)
        return min(max(target, self.NOTES_DEFAULT_MIN), self.NOTES_DEFAULT_MAX)

    def apply_notes_width(self, width: int) -> None:
        """Give the notes pane ``width`` pixels and the document pane the rest.

        The splitter scales the requested sizes when they do not fill it, so the
        span is measured from the widget rather than passed in: a pane width that
        was valid before a resize must not come back as a different number.
        """
        span = self.splitter_span()
        if span <= 0:
            # Not laid out yet; a self-consistent request is scaled on show.
            span = width + self.PDF_MIN_WIDTH
        document_width = max(span - width, self.PDF_MIN_WIDTH)
        self.notes_splitter.setSizes([width, document_width])
        self._last_notes_width = width

    def splitter_span(self) -> int:
        """Return the pixels the two panes share, excluding the splitter handle.

        ``setSizes`` distributes exactly this much, so asking for pane widths
        that add up to anything else makes Qt scale them -- and a 640px pane
        comes back as 636.
        """
        span = self.notes_splitter.width() - self.notes_splitter.handleWidth() * (self.notes_splitter.count() - 1)
        return span if span > 0 else 0

    # -- visibility ----------------------------------------------------------------

    def set_notes_panel_visible(self, visible: bool) -> None:
        """Show or hide the notes pane, keeping its width for the next toggle."""
        self.notes_visible = visible
        if visible:
            self.notes_panel.setVisible(True)
            self.apply_notes_width(self._last_notes_width)
        else:
            sizes = self.notes_splitter.sizes()
            dragged = sizes[0] if len(sizes) == 2 else 0
            if dragged >= self.NOTES_MIN_WIDTH:
                self._last_notes_width = dragged
            self.notes_panel.setVisible(False)
        self.sync_notes_action()
        self.save_notes_settings()

    def sync_notes_action(self) -> None:
        """Keep the menu toggle in step with the panel.

        The drag-driven auto-hide hides the panel without going through the
        action, so the checkmark has to be corrected from here. Signals are
        blocked because the action's own ``toggled`` is what calls back in.
        """
        if self.notes_action is None or self.notes_action.isChecked() == self.notes_visible:
            return
        self.notes_action.blockSignals(True)
        self.notes_action.setChecked(self.notes_visible)
        self.notes_action.blockSignals(False)

    # -- drag handling -------------------------------------------------------------

    def notes_splitter_moved(self, position: int, index: int) -> None:
        """Record a drag and arm the debounce that decides what to do with it."""
        del index  # Only the horizontal handle's position matters here.
        self._dragged_notes_width = position
        self._notes_drag_pending = True
        # Wait for the drag to finish: hiding the pane while the handle is still
        # under the mouse fights the drag it is reacting to.
        self._notes_auto_hide_timer.start()

    def finish_notes_drag(self) -> None:
        """Hide the pane when a drag left it below the auto-hide threshold."""
        if not self._notes_drag_pending:
            return
        self._notes_drag_pending = False
        if self._dragged_notes_width < self.auto_hide_width():
            self.set_notes_panel_visible(False)
            return
        # Remember only usable widths, so a collapse can never become the size
        # the next toggle restores.
        self._last_notes_width = self._dragged_notes_width
        self.save_notes_settings()

    def auto_hide_width(self) -> int:
        """Return the pane width, in pixels, below which the panel hides itself."""
        return max(int(self.notes_splitter.width() * self.NOTES_AUTO_HIDE_RATIO), 1)

    # -- lifecycle -----------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        """Apply the first-run 30% default once the splitter has a real width."""
        super().resizeEvent(event)
        if self._notes_first_run and self.notes_splitter.width() > 0:
            self._notes_first_run = False
            self.apply_default_notes_layout(self.reference_window_width())
