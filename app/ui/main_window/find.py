"""In-document text search: the find toolbar and the key that dismisses it.

Find is the only feature that needs a bare window ``QShortcut``: every other
shortcut is a menu ``QAction`` so the command palette can enumerate it. That is
why the single ``QShortcut`` registration lives here, next to the bar it hides.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QLabel, QLineEdit, QToolBar

from app.ui.main_window.theme import ThemeMixin
from app.ui.viewer_tab import PDFViewerWidget


class FindMixin(ThemeMixin):
    """Own the hidden find bar, its query field, and its ``Esc`` shortcut.

    Layer 3 of the window mixin chain (after ``ThemeMixin``).
    """

    find_bar: QToolBar
    find_input: QLineEdit
    find_status: QLabel
    escape_shortcut: QShortcut

    def create_find_bar(self) -> None:
        """Create the hidden top toolbar that hosts document search."""
        self.find_bar = QToolBar("Find", self)
        self.find_bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.find_bar)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find in document")
        self.find_input.setMinimumWidth(240)
        self.find_input.returnPressed.connect(self.find_next)

        self.find_status = QLabel()
        self.find_bar.addWidget(self.find_input)
        self.find_bar.addWidget(self.find_status)
        self.find_bar.setVisible(False)

    def create_shortcuts(self) -> None:
        """Register window-level shortcuts that are not part of a menu action."""
        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.escape_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.escape_shortcut.activated.connect(self.hide_find_bar)

    def show_find_bar(self) -> None:
        """Reveal the find bar and focus its query field."""
        if self.tabs.count() == 0:
            return
        self.find_bar.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find_bar(self) -> None:
        """Hide the find bar and remove every match highlight."""
        if not self.find_bar.isVisible():
            return
        self.find_bar.setVisible(False)
        self.find_input.clear()
        self.find_status.clear()
        viewer = self.tabs.currentWidget()
        if isinstance(viewer, PDFViewerWidget):
            viewer.clear_find()
            viewer.focus_canvas()

    def find_next(self) -> None:
        """Search the active document for the text in the find field."""
        viewer = self.tabs.currentWidget()
        if not isinstance(viewer, PDFViewerWidget):
            return
        query = self.find_input.text().strip()
        if not query:
            viewer.clear_find()
            self.find_status.clear()
            return
        matches = viewer.find(query)
        if matches:
            label = "match" if matches == 1 else "matches"
            self.find_status.setText(f"{matches} {label} on page {viewer.current_page + 1}")
        else:
            self.find_status.setText("No matches")
