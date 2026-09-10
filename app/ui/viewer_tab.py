"""Single-page PDF viewer widget."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from app.core.pdf_engine import RenderEngine


class PDFViewerWidget(QWidget):
    """Display the current PDF page and render it when the viewport needs it."""

    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self.engine = RenderEngine(file_path)
        self._disposed = False
        self.current_page = 0
        self.page_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.page_label.setText("Rendering page...")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.page_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

    def render_current_page(self) -> None:
        """Render the active page at the current viewport size."""
        viewport_size = self.scroll_area.viewport().size()
        image = self.engine.render_page(self.current_page, viewport_size)
        self.page_label.setPixmap(QPixmap.fromImage(image))
        self.page_label.adjustSize()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.render_current_page()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.isVisible():
            self.render_current_page()

    def dispose(self) -> None:
        """Release the PDF document when this viewer is removed from a tab."""
        if not self._disposed:
            self.engine.close()
            self._disposed = True

    def closeEvent(self, event) -> None:
        self.dispose()
        super().closeEvent(event)