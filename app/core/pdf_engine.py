"""PyMuPDF document access and active-page rasterization."""

from pathlib import Path

import numpy as np
import pymupdf
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage


class RenderEngine:
    """Open a PDF and render one requested page to fit a viewport."""

    _dark_gray_lut = np.rint(
        np.array([239.0, 239.0, 244.0])
        + (
            np.array([46.0, 52.0, 64.0]) - np.array([239.0, 239.0, 244.0])
        )
        * (3.0 * (np.arange(256)[:, None] / 255.0) ** 2 - 2.0 * (np.arange(256)[:, None] / 255.0) ** 3)
    ).astype(np.uint8)

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.document = pymupdf.open(file_path)

    @property
    def page_count(self) -> int:
        """Return the number of pages in the open document."""
        return self.document.page_count

    def render_page(self, page_number: int, viewport_size: QSize, dark_mode: bool = False) -> QImage:
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
        if dark_mode:
            return self.transform_for_dark_mode(image)
        return image.copy()

    @staticmethod
    def transform_for_dark_mode(image: QImage) -> QImage:
        """Transform page pixels in bulk without mutating Qt-owned memory."""
        source = image.convertToFormat(QImage.Format.Format_RGB888)
        height, width = source.height(), source.width()
        byte_count = source.bytesPerLine() * height
        buffer = np.frombuffer(source.constBits(), dtype=np.uint8, count=byte_count)
        rows = buffer.reshape(height, source.bytesPerLine())[:, : width * 3]
        rgb = rows.reshape(height, width, 3).copy()
        maximum = np.max(rgb, axis=2)
        minimum = np.min(rgb, axis=2)
        chroma = maximum.astype(np.int16) - minimum.astype(np.int16)
        neutral = chroma < 30

        luminance = np.rint(rgb.mean(axis=2)).astype(np.uint8)
        grayscale = RenderEngine._dark_gray_lut[luminance]
        result = np.where(neutral[..., None], grayscale, rgb)

        # Keep colored tokens recognizable while lifting only dark colors.
        colored = ~neutral
        if np.any(colored):
            colored_pixels = result[colored].astype(np.float32)
            colored_min = colored_pixels.min(axis=1)
            colored_max = colored_pixels.max(axis=1)
            dark = colored_max < 190.0
            lift = np.ones_like(colored_max)
            lift[dark] = 190.0 / np.maximum(colored_max[dark], 1.0)
            colored_pixels = np.clip(colored_pixels * lift[:, None], 0.0, 255.0)
            result[colored] = colored_pixels.astype(np.uint8)

        output = np.ascontiguousarray(result, dtype=np.uint8)
        return QImage(output.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()

    def close(self) -> None:
        """Release the underlying document handle."""
        self.document.close()