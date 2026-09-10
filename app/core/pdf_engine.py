"""PyMuPDF document access and active-page rasterization."""

from pathlib import Path

import pymupdf
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage


class RenderEngine:
    """Open a PDF and render one requested page to fit a viewport."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.document = pymupdf.open(file_path)

    @property
    def page_count(self) -> int:
        """Return the number of pages in the open document."""
        return self.document.page_count

    def render_page(self, page_number: int, viewport_size: QSize) -> QImage:
        """Rasterize only ``page_number`` at the scale needed by the viewport."""
        if not 0 <= page_number < self.page_count:
            raise IndexError(f"Page index out of range: {page_number}")

        page = self.document.load_page(page_number)
        page_size = page.rect
        available_width = max(viewport_size.width() - 32, 1)
        available_height = max(viewport_size.height() - 32, 1)
        scale = min(
            available_width / page_size.width,
            available_height / page_size.height,
        )
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        image = QImage(
            pixmap.samples,
            pixmap.width,
            pixmap.height,
            pixmap.stride,
            QImage.Format.Format_RGB888,
        )
        return image.copy()

    def close(self) -> None:
        """Release the underlying document handle."""
        self.document.close()