"""Page position and magnification for the active document.

Everything here reads its target through :meth:`NavigationMixin.current_viewer`,
so a control never has to care which tab is active or whether a document is open
at all.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QLabel, QLineEdit, QSizePolicy, QToolBar, QWidget

from app.ui.main_window.bookmarks import BookmarksMixin
from app.ui.viewer_tab import PDFViewerWidget


class NavigationMixin(BookmarksMixin):
    """The bottom page bar, page turning, and zoom.

    Layer 5 of the window mixin chain (after ``BookmarksMixin``).
    """

    bottom_bar: QToolBar
    page_input: QLineEdit
    page_status: QLabel

    def create_bottom_bar(self) -> None:
        """Create centered page navigation controls in a bottom toolbar."""
        self.bottom_bar = QToolBar("Page Navigation", self)
        self.bottom_bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.bottom_bar)

        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("Page")
        self.page_input.setMaximumWidth(90)
        self.page_input.setValidator(QIntValidator(1, 1, self.page_input))
        self.page_input.returnPressed.connect(self.go_to_page)

        self.page_status = QLabel()
        self.bottom_bar.addWidget(left_spacer)
        self.bottom_bar.addWidget(self.page_input)
        self.bottom_bar.addWidget(self.page_status)
        self.bottom_bar.addWidget(right_spacer)

    def connect_viewer(self, viewer: PDFViewerWidget) -> None:
        """Connect one viewer's page and zoom state to the window controls."""
        viewer.page_changed.connect(self.update_page_status)
        viewer.zoom_changed.connect(self.show_zoom)

    def update_page_controls(self, tab_index: int) -> None:
        """Refresh page controls when the active document changes."""
        if tab_index < 0:
            self.page_input.clear()
            self.page_status.clear()
            return
        viewer = self.tabs.widget(tab_index)
        if isinstance(viewer, PDFViewerWidget):
            self.update_page_status(viewer.current_page, viewer.engine.page_count)

    def update_page_status(self, current_page: int, page_count: int) -> None:
        """Display the active page as a one-based position and total."""
        self.page_input.setText(str(current_page + 1))
        self.page_status.setText(f"of {page_count}")
        self.page_input.setValidator(QIntValidator(1, page_count, self.page_input))

    def go_to_page(self) -> None:
        """Navigate the active tab to the page entered by the user."""
        viewer = self.current_viewer()
        if viewer is None:
            return
        page_number = self.page_input.text().strip()
        if page_number:
            viewer.set_page(int(page_number) - 1)

    def focus_page_input(self) -> None:
        """Focus the page-number field so a destination can be typed."""
        if self.tabs.count() == 0:
            return
        self.page_input.setFocus()
        self.page_input.selectAll()

    def current_viewer(self) -> PDFViewerWidget | None:
        """Return the active document viewer, or ``None`` when no document is open."""
        viewer = self.tabs.currentWidget()
        return viewer if isinstance(viewer, PDFViewerWidget) else None

    def next_page(self) -> None:
        """Advance the active document by one page."""
        viewer = self.current_viewer()
        if viewer is not None:
            viewer.next_page()

    def previous_page(self) -> None:
        """Move the active document back by one page."""
        viewer = self.current_viewer()
        if viewer is not None:
            viewer.previous_page()

    def zoom_in(self) -> None:
        """Magnify the active document by one zoom step."""
        viewer = self.current_viewer()
        if viewer is not None:
            viewer.zoom_in()

    def zoom_out(self) -> None:
        """Shrink the active document by one zoom step."""
        viewer = self.current_viewer()
        if viewer is not None:
            viewer.zoom_out()

    def reset_zoom(self) -> None:
        """Restore fit-to-page magnification for the active document."""
        viewer = self.current_viewer()
        if viewer is not None:
            viewer.reset_zoom()

    def show_zoom(self, zoom: float) -> None:
        """Report the current magnification in the status bar."""
        self.statusBar().showMessage(f"Zoom {zoom * 100:.0f}%", self.STATUS_TIMEOUT_MS)
