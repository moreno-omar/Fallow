"""Single-page PDF viewer widget."""

from pathlib import Path

import pymupdf
from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut, QWheelEvent
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from app.core.pdf_engine import RenderEngine


class PDFViewerWidget(QWidget):
    """Display the current PDF page and render it when the viewport needs it."""

    page_changed = Signal(int, int)
    zoom_changed = Signal(float)

    MIN_ZOOM = 0.25
    MAX_ZOOM = 4.0
    ZOOM_STEP = 1.15

    def __init__(self, file_path: Path, dark_mode: bool = False) -> None:
        super().__init__()
        self.engine = RenderEngine(file_path)
        self._disposed = False
        self.current_page = 0
        self.dark_mode = dark_mode
        self.zoom = 1.0
        self.bookmarks: dict[int, int] = {}
        self._wheel_delta = 0
        self._find_query = ""
        self._match_page = -1
        self._match_rects: list[pymupdf.Rect] = []
        self._active_match = -1
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
        """Render the active page with the current size, zoom, and search matches."""
        if self._match_page == self.current_page:
            highlights: list[pymupdf.Rect] = self._match_rects
            active_highlight = self._active_match
        else:
            highlights = []
            active_highlight = -1
        image = self.engine.render_page(
            self.current_page,
            self.scroll_area.viewport().size(),
            self.dark_mode,
            self.zoom,
            highlights,
            active_highlight,
        )
        pixmap = QPixmap.fromImage(image)
        self.page_label.setPixmap(pixmap)
        # A magnified page must be allowed to grow past the viewport so the
        # scroll area shows scroll bars instead of clipping the page.
        self.page_label.setMinimumSize(pixmap.size() if self.zoom > 1.0 else QSize(0, 0))
        self.page_label.adjustSize()

    def set_zoom(self, zoom: float) -> None:
        """Apply a clamped magnification factor and repaint the active page."""
        clamped = min(max(zoom, self.MIN_ZOOM), self.MAX_ZOOM)
        if clamped == self.zoom or self._disposed:
            return
        self.zoom = clamped
        self.render_current_page()
        self.zoom_changed.emit(self.zoom)

    def zoom_in(self) -> None:
        """Magnify the page by one step."""
        self.set_zoom(self.zoom * self.ZOOM_STEP)

    def zoom_out(self) -> None:
        """Shrink the page by one step."""
        self.set_zoom(self.zoom / self.ZOOM_STEP)

    def reset_zoom(self) -> None:
        """Return to fit-to-page magnification."""
        self.set_zoom(1.0)

    def find(self, text: str) -> int:
        """Highlight the next occurrence of ``text``, wrapping at the document end.

        Returns the number of matches on the page that was located, or ``0`` when
        the text does not occur anywhere in the document.
        """
        query = text.strip()
        if not query:
            self.clear_find()
            return 0

        start_page = self.current_page
        if query == self._find_query and self._match_page == self.current_page:
            if self._active_match + 1 < len(self._match_rects):
                self._active_match += 1
                self.render_current_page()
                return len(self._match_rects)
            start_page = self.current_page + 1

        self._find_query = query
        for offset in range(self.engine.page_count):
            page_number = (start_page + offset) % self.engine.page_count
            matches = self.engine.search_page(page_number, query)
            if not matches:
                continue
            self._match_page = page_number
            self._match_rects = matches
            self._active_match = 0
            if page_number == self.current_page:
                self.render_current_page()
                self.page_changed.emit(self.current_page, self.engine.page_count)
            else:
                self.set_page(page_number)
            return len(matches)

        self.clear_find()
        return 0

    def clear_find(self) -> None:
        """Forget stored matches and repaint the page without highlights."""
        had_matches = bool(self._match_rects)
        self._find_query = ""
        self._match_page = -1
        self._match_rects = []
        self._active_match = -1
        if had_matches and not self._disposed:
            self.render_current_page()

    def toggle_bookmark(self) -> bool:
        """Toggle a location pointer for the active page.

        Returns ``True`` when a bookmark was added and ``False`` when one was
        removed. This is the Phase 12 scaffold: pointers live in memory only,
        because persistent storage and the bookmarks dock are not built yet.
        """
        if self.current_page in self.bookmarks:
            del self.bookmarks[self.current_page]
            return False
        pointer = self.engine.make_bookmark(self.current_page)
        if pointer is None:
            return False
        self.bookmarks[self.current_page] = pointer
        return True

    def bookmark_pages(self) -> list[int]:
        """Return the zero-based pages bookmarked in this document, in order."""
        return sorted(self.bookmarks)

    def focus_canvas(self) -> None:
        """Give keyboard focus back to the rendered page area."""
        self.scroll_area.setFocus()

    def set_dark_mode(self, enabled: bool) -> None:
        """Change page rendering theme and refresh the active page."""
        self.dark_mode = enabled
        if self.isVisible() and not self._disposed:
            self.render_current_page()

    def set_page(self, page_number: int) -> None:
        """Show a zero-based page number after clamping it to the document."""
        target_page = min(max(page_number, 0), self.engine.page_count - 1)
        if target_page == self.current_page:
            self.page_changed.emit(self.current_page, self.engine.page_count)
            return
        self.current_page = target_page
        self.render_current_page()
        self.page_changed.emit(self.current_page, self.engine.page_count)

    def next_page(self) -> None:
        """Advance one page without exceeding the document boundary."""
        if self.current_page < self.engine.page_count - 1:
            self.set_page(self.current_page + 1)

    def previous_page(self) -> None:
        """Move back one page without going below the first page."""
        if self.current_page > 0:
            self.set_page(self.current_page - 1)

    def eventFilter(self, watched, event) -> bool:
        """Route wheel input to page navigation, or to zoom while Ctrl is held."""
        if watched in (self.scroll_area, self.scroll_area.viewport()) and event.type() == QEvent.Type.Wheel:
            wheel_event = event
            if isinstance(wheel_event, QWheelEvent):
                if wheel_event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self._wheel_delta = 0
                    self.zoom_by_wheel(wheel_event.angleDelta().y())
                    wheel_event.accept()
                    return True
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

    def zoom_by_wheel(self, angle_delta: int) -> None:
        """Convert one wheel delta into one zoom step in the matching direction."""
        if angle_delta == 0:
            return
        steps = self.ZOOM_STEP ** (1 if angle_delta > 0 else -1)
        self.set_zoom(self.zoom * steps)

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