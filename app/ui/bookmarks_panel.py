"""The bookmarks pane: the document outline above the reader's own marks.

The pane answers the two questions a bookmark panel is for -- "where can I go in
this document?" and "where did I leave a mark?" -- so it stacks two views:

* an outline ``QTreeView`` fed by PyMuPDF's table of contents, and
* a marks ``QListWidget`` fed by the ``bookmarks`` table in SQLite.

They share one ``QSplitter`` because the sidebar is already a ``QTabWidget``: the
Phase 13 sketch first drew outline and marks as two more tabs, but a second tab
row costs vertical space in a pane that is only as wide as 30% of the window.
Neither view owns data -- the pane is told what to show and reports what the
reader picked.
"""

from collections.abc import Sequence

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from app.core.database import Bookmark

# PyMuPDF's ``Document.get_toc()`` rows: ``[level, title, page]``. The page is
# one-based here and ``-1`` (a heading with no destination) is allowed.
OutlineEntry = tuple[int, str, int]


class BookmarksPanel(QWidget):
    """Outline + saved marks for the active document.

    Signals:
        page_requested: emitted with a *zero-based* page the reader activated.
        mark_removed: emitted with a zero-based page whose mark should be deleted.
    """

    page_requested = Signal(int)
    mark_removed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the headers and the two views."""
        super().__init__(parent)
        self.setObjectName("bookmarksPanel")
        # A plain QWidget paints a stylesheet background only when this
        # attribute is set, which the dark theme relies on.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.outline_view = QTreeView()
        self.outline_view.setObjectName("outlineView")
        self.outline_view.setHeaderHidden(True)
        self.outline_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.outline_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.outline_model = QStandardItemModel(self.outline_view)
        self.outline_view.setModel(self.outline_model)
        self.outline_view.activated.connect(self.outline_activated)

        self.marks_list = QListWidget()
        self.marks_list.setObjectName("marksList")
        self.marks_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.marks_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.marks_list.itemActivated.connect(self.mark_activated)
        # Scoped to the list so Delete keeps working as a normal key elsewhere.
        self.remove_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.marks_list)
        self.remove_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.remove_shortcut.activated.connect(self.remove_current_mark)

        # What the views currently show, so an unchanged refresh can skip the
        # rebuild instead of re-creating items and dropping the reader's place.
        self._outline_entries: list[OutlineEntry] = []
        self._marks: list[tuple[int, str | None]] = []

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.build_section("Contents", self.outline_view))
        splitter.addWidget(self.build_section("Bookmarks", self.marks_list))
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    @staticmethod
    def build_section(title: str, view: QWidget) -> QWidget:
        """Wrap one view with its heading so both sections look alike."""
        section = QWidget()
        section.setObjectName("bookmarksSection")
        header = QLabel(title)
        header.setObjectName("panelHeader")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        layout.addWidget(header)
        layout.addWidget(view, 1)
        return section

    # -- interaction ---------------------------------------------------------------

    def outline_activated(self, index: QModelIndex) -> None:
        """Report the destination of the activated outline row."""
        page = index.data(Qt.ItemDataRole.UserRole)
        if isinstance(page, int):
            self.page_requested.emit(page)

    def mark_activated(self, item: QListWidgetItem) -> None:
        """Report the page of the activated mark."""
        page = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(page, int):
            self.page_requested.emit(page)

    def remove_current_mark(self) -> None:
        """Ask for the selected mark's page to be deleted."""
        item = self.marks_list.currentItem()
        if item is None:
            return
        page = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(page, int):
            self.mark_removed.emit(page)

    # -- content -------------------------------------------------------------------

    def clear(self) -> None:
        """Empty both views, for when no document is open."""
        self.outline_model.clear()
        self.marks_list.clear()
        self._outline_entries = []
        self._marks = []

    def set_outline(self, entries: Sequence[OutlineEntry]) -> None:
        """Rebuild the outline tree from PyMuPDF ``(level, title, page)`` rows.

        Levels nest: a row always attaches to the closest previous row with a
        smaller level, which is how the flat table of contents becomes a tree.
        The rebuild is skipped when the tree already shows exactly these rows, so
        moving between documents keeps the reader's expansion state.
        """
        rows = list(entries)
        if rows == self._outline_entries:
            return
        self._outline_entries = rows
        self.outline_model.clear()
        open_rows: list[QStandardItem] = []
        for level, title, page in rows:
            if level < 1:
                continue
            item = QStandardItem(title)
            item.setEditable(False)
            item.setToolTip(title)
            # Store zero-based pages; a heading without a destination stays None
            # so activating it does nothing instead of jumping to page 0.
            item.setData(page - 1 if page >= 1 else None, Qt.ItemDataRole.UserRole)
            while len(open_rows) >= level:
                open_rows.pop()
            if open_rows:
                open_rows[-1].appendRow(item)
            else:
                self.outline_model.appendRow(item)
            open_rows.append(item)
        self.outline_view.expandAll()

    def set_marks(self, bookmarks: Sequence[Bookmark]) -> None:
        """Rebuild the marks list from one book's stored bookmarks."""
        rows = [(bookmark.page, bookmark.label) for bookmark in bookmarks]
        if rows == self._marks:
            return
        self._marks = rows
        self.marks_list.clear()
        for bookmark in bookmarks:
            item = QListWidgetItem(bookmark.label or f"Page {bookmark.page + 1}")
            item.setData(Qt.ItemDataRole.UserRole, bookmark.page)
            item.setToolTip(bookmark.label or f"Page {bookmark.page + 1}")
            self.marks_list.addItem(item)

    def mark_count(self) -> int:
        """Return how many marks the list currently shows."""
        return self.marks_list.count()

    def focus_default_view(self) -> None:
        """Give the keyboard to the marks list, the reason the pane is opened."""
        self.marks_list.setFocus()
