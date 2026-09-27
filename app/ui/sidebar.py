"""The left sidebar: one panel holding the bookmarks and notes tabs.

Both panels always exist and are always reachable; the sidebar is only ever
hidden as a whole (``Ctrl+Shift+E`` / ``F9``). The tab bar is hidden when just one
tab is visible, so a future single-pane layout does not leave a lone tab
floating above the content, and the reader keeps the full pane height.

The widget owns no persistence: the active tab is read back by name through
:meth:`active_tab_name` and restored with :meth:`set_active_tab`, and the window
stores it in ``QSettings`` next to the pane width and visibility.
"""

from PySide6.QtWidgets import QTabWidget, QWidget

from app.ui.bookmarks_panel import BookmarksPanel
from app.ui.notes_panel import NotesPanel

# Stable tab names. The window stores the active one in ``QSettings``, so these
# strings must not change when the tabs are reordered.
BOOKMARKS_TAB = "bookmarks"
NOTES_TAB = "notes"


class Sidebar(QTabWidget):
    """Tabbed container for the bookmarks pane and the notes pane."""

    BOOKMARKS_INDEX = 0
    NOTES_INDEX = 1
    # Stable names so a saved tab survives any future reordering of the tabs.
    TAB_NAMES = (BOOKMARKS_TAB, NOTES_TAB)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build both panes and their tab entries."""
        super().__init__(parent)
        self.setObjectName("sidebar")
        # A document-mode tab bar is flat and sits flush with the pane, which is
        # what a sidebar wants; the document tab strip keeps its own styling.
        self.setDocumentMode(True)

        self.bookmarks_panel = BookmarksPanel()
        self.notes_panel = NotesPanel()
        self.insertTab(self.BOOKMARKS_INDEX, self.bookmarks_panel, "Bookmarks")
        self.insertTab(self.NOTES_INDEX, self.notes_panel, "Notes")
        self.setTabToolTip(self.BOOKMARKS_INDEX, "Outline and saved page marks")
        self.setTabToolTip(self.NOTES_INDEX, "Notes for the active document")

        self.currentChanged.connect(self.sync_tab_bar_visibility)
        self.sync_tab_bar_visibility()

    def sync_tab_bar_visibility(self, *_args: object) -> None:
        """Hide the tab strip while fewer than two tabs are visible."""
        visible_tabs = sum(1 for index in range(self.count()) if self.isTabVisible(index))
        self.tabBar().setVisible(visible_tabs > 1)

    def setTabVisible(self, index: int, visible: bool) -> None:
        """Hide or show one tab and re-evaluate the tab strip.

        Qt has no "tab visibility changed" signal, so the rule "hide the tab bar
        when only one tab is on show" has to be re-applied from the one call that
        can change it.
        """
        super().setTabVisible(index, visible)
        self.sync_tab_bar_visibility()

    def active_tab_name(self) -> str:
        """Return the stable name of the selected tab."""
        index = self.currentIndex()
        if 0 <= index < len(self.TAB_NAMES):
            return self.TAB_NAMES[index]
        return self.TAB_NAMES[self.BOOKMARKS_INDEX]

    def set_active_tab(self, name: str) -> None:
        """Select a tab by its stable name, ignoring an unknown name."""
        if name not in self.TAB_NAMES:
            return
        self.setCurrentIndex(self.TAB_NAMES.index(name))

    def focus_active_panel(self) -> None:
        """Give the keyboard to the view inside the selected tab."""
        widget = self.currentWidget()
        if isinstance(widget, BookmarksPanel):
            widget.focus_default_view()
        elif isinstance(widget, NotesPanel):
            widget.focus_default_view()
