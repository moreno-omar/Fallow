"""PyMuPDF document access and active-page rasterization."""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pymupdf
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage


class RenderEngine:
    """Open a PDF and render one requested page to fit a viewport."""

    # Search markers: passive matches stay subtle, the active match stands out.
    _highlight_color = {"light": (255, 235, 59), "dark": (136, 192, 208)}
    _active_highlight_color = {"light": (255, 152, 0), "dark": (235, 203, 139)}
    _passive_alpha = 0.32
    _active_alpha = 0.55

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

    def render_page(
        self,
        page_number: int,
        viewport_size: QSize,
        dark_mode: bool = False,
        zoom: float = 1.0,
        highlights: Sequence[pymupdf.Rect] = (),
        active_highlight: int = -1,
    ) -> QImage:
        """Rasterize one page to fit the viewport at the requested magnification.

        The ``pymupdf.Matrix`` scale is the fit-to-viewport scale multiplied by
        ``zoom``, so a zoom of ``1.0`` keeps the fit-to-page behaviour. Matches in
        ``highlights`` (page-space rectangles) are blended into the raster after
        colour processing, with ``active_highlight`` marking the current match.
        """
        if not 0 <= page_number < self.page_count:
            raise IndexError(f"Page index out of range: {page_number}")

        page = self.document.load_page(page_number)
        page_size = page.rect
        available_width = max(viewport_size.width() - 32, 1)
        available_height = max(viewport_size.height() - 32, 1)
        fit_scale = min(
            available_width / page_size.width,
            available_height / page_size.height,
        )
        scale = fit_scale * max(zoom, 0.01)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        image = QImage(
            pixmap.samples,
            pixmap.width,
            pixmap.height,
            pixmap.stride,
            QImage.Format.Format_RGB888,
        )
        rendered = self.transform_for_dark_mode(image) if dark_mode else image.copy()
        if highlights:
            rendered = self.highlight_matches(
                rendered,
                highlights,
                scale,
                dark_mode,
                active_highlight,
            )
        return rendered

    @classmethod
    def highlight_matches(
        cls,
        image: QImage,
        highlights: Sequence[pymupdf.Rect],
        scale: float,
        dark_mode: bool = False,
        active_highlight: int = -1,
    ) -> QImage:
        """Blend translucent markers for search matches into a rendered page."""
        mode = "dark" if dark_mode else "light"
        passive_color = np.array(cls._highlight_color[mode], dtype=np.float32)
        active_color = np.array(cls._active_highlight_color[mode], dtype=np.float32)

        source = image.convertToFormat(QImage.Format.Format_RGB888)
        height, width = source.height(), source.width()
        byte_count = source.bytesPerLine() * height
        buffer = np.frombuffer(source.constBits(), dtype=np.uint8, count=byte_count)
        rows = buffer.reshape(height, source.bytesPerLine())[:, : width * 3]
        rgb = rows.reshape(height, width, 3).copy()

        for index, rect in enumerate(highlights):
            is_active = index == active_highlight
            color = active_color if is_active else passive_color
            alpha = cls._active_alpha if is_active else cls._passive_alpha
            x0 = max(int(rect.x0 * scale), 0)
            y0 = max(int(rect.y0 * scale), 0)
            x1 = min(int(np.ceil(rect.x1 * scale)), width)
            y1 = min(int(np.ceil(rect.y1 * scale)), height)
            if x1 <= x0 or y1 <= y0:
                continue
            window = rgb[y0:y1, x0:x1].astype(np.float32)
            rgb[y0:y1, x0:x1] = np.clip(
                window * (1.0 - alpha) + color * alpha,
                0.0,
                255.0,
            ).astype(np.uint8)

        output = np.ascontiguousarray(rgb)
        return QImage(output.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()

    def search_page(self, page_number: int, text: str) -> list[pymupdf.Rect]:
        """Return page-space rectangles for every occurrence of ``text`` on a page."""
        if not text.strip() or not 0 <= page_number < self.page_count:
            return []
        return self.document.load_page(page_number).search_for(text)

    def make_bookmark(self, page_number: int) -> int | None:
        """Return a PyMuPDF location pointer for ``page_number``.

        ``Document.make_bookmark`` converts a ``(chapter, page)`` location into an
        opaque pointer that can be resolved again with ``Document.find_bookmark``.
        PDFs are single-chapter documents, so the chapter is always ``0``. Only the
        pointer creation is scaffolded here; persistence lands in Phase 12.
        """
        if not 0 <= page_number < self.page_count:
            return None
        return self.document.make_bookmark((0, page_number))

    @staticmethod
    def transform_for_dark_mode(image: QImage) -> QImage:
        """Transform page pixels with continuous colored-edge blending."""
        source = image.convertToFormat(QImage.Format.Format_RGB888)
        height, width = source.height(), source.width()
        byte_count = source.bytesPerLine() * height
        buffer = np.frombuffer(source.constBits(), dtype=np.uint8, count=byte_count)
        rows = buffer.reshape(height, source.bytesPerLine())[:, : width * 3]
        rgb = rows.reshape(height, width, 3).copy()
        maximum = np.max(rgb, axis=2).astype(np.float32)
        minimum = np.min(rgb, axis=2).astype(np.float32)
        chroma = maximum - minimum

        luminance = np.rint(rgb.mean(axis=2)).astype(np.uint8)
        grayscale = RenderEngine._dark_gray_lut[luminance].astype(np.float32)

        # Blend through the antialiased edge instead of cutting at one chroma.
        chroma_weight = np.clip((chroma - 15.0) / 40.0, 0.0, 1.0)
        chroma_weight = chroma_weight * chroma_weight * (3.0 - 2.0 * chroma_weight)
        lifted_colors = 255.0 - rgb.astype(np.float32)
        result = (
            (1.0 - chroma_weight[..., None]) * grayscale
            + chroma_weight[..., None] * lifted_colors
        )

        output = np.ascontiguousarray(np.clip(result, 0.0, 255.0), dtype=np.uint8)
        return QImage(output.data, width, height, width * 3, QImage.Format.Format_RGB888).copy()

    def close(self) -> None:
        """Release the underlying document handle."""
        self.document.close()