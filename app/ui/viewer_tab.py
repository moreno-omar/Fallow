"""Single-page PDF viewer widget."""

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut, QWheelEvent
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from app.core.pdf_engine import RenderEngine


class PDFViewerWidget(QWidget):
    """Display the current PDF page and render it when the viewport needs it."""

    def __init__(self, file_path: Path) -> None:
        super().__init__()
        self.engine = RenderEngine(file_path)
        self._disposed = False
        self.current_page = 0
        self._wheel_delta = 0
        self.page_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self.page_label.setText("Rendering page...")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.page_label)
        self.scroll_area.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)

        self._shortcuts = []
        for key, handler in (
            (QKeySequence(Qt.Key.Key_Right), self.next_page),
            (QKeySequence(Qt.Key.Key_Down), self.next_page),
            (QKeySequence(Qt.Key.Key_PageDown), self.next_page),
            (QKeySequence(Qt.Key.Key_Left), self.previous_page),
            (QKeySequence(Qt.Key.Key_Up), self.previous_page),
            (QKeySequence(Qt.Key.Key_PageUp), self.previous_page),
        ):
            shortcut = QShortcut(key, self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll_area)

    def render_current_page(self) -> None:
        """Render the active page at the current viewport size."""
        viewport_size = self.scroll_area.viewport().size()
        image = self.engine.render_page(self.current_page, viewport_size)
        self.page_label.setPixmap(QPixmap.fromImage(image))
        self.page_label.adjustSize()

    def next_page(self) -> None:
        """Advance one page without exceeding the document boundary."""
        if self.current_page < self.engine.page_count - 1:
            self.current_page += 1
            self.render_current_page()

    def previous_page(self) -> None:
        """Move back one page without going below the first page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.render_current_page()

    def eventFilter(self, watched, event) -> bool:
        """Route wheel input from the scroll area to discrete page navigation."""
        if watched in (self.scroll_area, self.scroll_area.viewport()) and event.type() == QEvent.Type.Wheel:
            wheel_event = event
            if isinstance(wheel_event, QWheelEvent):
                self._wheel_delta += wheel_event.angleDelta().y()
                while abs(self._wheel_delta) >= 120:
                    if self._wheel_delta > 0:
                        self.previous_page()
                        self._wheel_delta -= 120
                    else:
                        self.next_page()
                        self._wheel_delta += 120
                wheel_event.accept()
                return True
        return super().eventFilter(watched, event)

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