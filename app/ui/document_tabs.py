"""Tab strip widgets: an eliding tab bar, an overflow list, and Tab Search.

Three small pieces keep the tab strip usable once many documents are open:

* :class:`DocumentTabBar` clamps every tab to a readable width, so Qt elides the
  title with an ellipsis, and shows a sliding window of at most five tabs. The
  tabs outside that window are hidden, not squeezed.
* :class:`TabOverflowButton` sits at the end of the bar and lists every open
  document, including the hidden ones.
* :class:`TabSearchDialog` is the keyboard version of that list (``Ctrl+Shift+A``).

The window owns the behaviour: these widgets only describe and report what the
user picked, so nothing here knows how a tab is closed or how a PDF is rendered.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QMenu, QTabBar, QToolButton, QWidget

from app.ui.command_palette import Command, CommandPalette


@dataclass(frozen=True)
class TabEntry:
    """One open document, as a tab list should show it.

    ``index`` is the tab index the window needs to focus, ``location`` is the
    absolute file path used as a tooltip, and ``active`` marks the tab the user
    is currently reading so the overflow menu can show it checked.
    """

    index: int
    title: str
    location: str
    page: int = 0
    page_count: int = 0
    active: bool = False

    @property
    def hint(self) -> str:
        """Return the reading position as a right-hand list label."""
        if self.page_count <= 0:
            return ""
        return f"page {self.page + 1} of {self.page_count}"


class DocumentTabBar(QTabBar):
    """Tab bar that elides long titles and keeps a sliding five-tab window.

    Qt sizes a tab bar to its tabs and shrinks them when the bar is narrow, so
    two independent limits are applied here:

    * every tab is clamped to ``MIN_TAB_WIDTH``-``MAX_TAB_WIDTH``, which is what
      makes Qt elide the title with an ellipsis (and switch on its scroll arrows
      once even the minimum widths no longer fit), and
    * only the ``MAX_VISIBLE_TABS`` tabs around the active one are shown.
      :meth:`sync_visible_window` hides the rest, so a long tab strip never
      squeezes every title down to a few unreadable pixels. Hidden documents stay
      reachable through the overflow button and through Tab Search.
    """

    MIN_TAB_WIDTH = 90
    MAX_TAB_WIDTH = 190
    MAX_VISIBLE_TABS = 5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setUsesScrollButtons(True)
        self.setMovable(False)
        self.setMaximumWidth(self.MAX_TAB_WIDTH * self.MAX_VISIBLE_TABS)
        self._syncing = False

    def tabSizeHint(self, index: int) -> QSize:
        """Clamp one tab between the minimum and the maximum readable width."""
        hint = super().tabSizeHint(index)
        width = min(max(hint.width(), self.MIN_TAB_WIDTH), self.MAX_TAB_WIDTH)
        return QSize(width, hint.height())

    def window_start(self, current: int) -> int:
        """Return the first index of the window that contains ``current``."""
        count = self.count()
        if count <= self.MAX_VISIBLE_TABS or current < 0:
            return 0
        # Slide only as far as needed: earlier tabs stay in place until the
        # active one would fall off the end of the window.
        return min(max(current - self.MAX_VISIBLE_TABS + 1, 0), count - self.MAX_VISIBLE_TABS)

    def sync_visible_window(self, current: int) -> None:
        """Show the tabs of the window around ``current`` and hide the others."""
        if self._syncing:
            return
        start = self.window_start(current)
        end = start + self.MAX_VISIBLE_TABS
        self._syncing = True
        try:
            # Reveal before hiding: Qt picks another current tab if the active
            # one becomes hidden, which would re-enter this method through
            # ``currentChanged`` and leave the wrong tab selected.
            for index in range(self.count()):
                if start <= index < end and not self.isTabVisible(index):
                    self.setTabVisible(index, True)
            for index in range(self.count()):
                if not (start <= index < end) and self.isTabVisible(index):
                    self.setTabVisible(index, False)
        finally:
            self._syncing = False


class TabOverflowButton(QToolButton):
    """Button at the end of the tab bar that lists every open document.

    The list is pulled from ``entries_provider`` every time the menu opens rather
    than cached, so adding or closing a tab never has to notify this widget.
    """

    document_selected = Signal(int)

    def __init__(self, entries_provider: Callable[[], Sequence[TabEntry]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries_provider = entries_provider
        self._menu = QMenu(self)
        self._menu.aboutToShow.connect(self.rebuild_menu)
        self.setArrowType(Qt.ArrowType.DownArrow)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setAutoRaise(True)
        self.setToolTip("List all open documents")
        self.setMenu(self._menu)
        self.rebuild_menu()

    def rebuild_menu(self) -> None:
        """Rebuild one checkable row per open document."""
        self._menu.clear()
        for entry in self._entries_provider():
            action = self._menu.addAction(entry.title)
            action.setCheckable(True)
            action.setChecked(entry.active)
            action.setToolTip(entry.location)
            # ``partial`` would forward the ``triggered`` bool into the signal,
            # so the index is bound through a default argument instead.
            action.triggered.connect(lambda _checked=False, index=entry.index: self.document_selected.emit(index))


class TabSearchDialog(CommandPalette):
    """Tab Search: the command palette, filled with the open documents.

    Filtering, keyboard handling, and accepting a row behave exactly like the
    command palette, and ``MainWindow`` builds the entries, so only the dialog
    title, the placeholder, and the list cap differ. A tab list has to be able to
    show the documents the tab bar is hiding, hence the larger cap than the eight
    rows the command palette keeps for its popup.
    """

    MAX_RESULTS = 20

    def __init__(
        self,
        commands: Sequence[Command],
        dark_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Build the list from one command per open document."""
        super().__init__(commands, dark_mode, parent)
        self.setWindowTitle("Tab Search")
        self.query_input.setPlaceholderText("Type a document name")
