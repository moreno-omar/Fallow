"""Reading marks on the active document.

This is the Phase 9 scaffold: a bookmark is a PyMuPDF location pointer kept in
memory for the lifetime of the viewer. The persistent JSON store and the
bookmarks dock planned for Phase 12 belong in this file, which is why the single
toggle already has its own layer.
"""

from app.ui.main_window.find import FindMixin
from app.ui.viewer_tab import PDFViewerWidget


class BookmarksMixin(FindMixin):
    """Toggle a bookmark on the current page of the active document.

    Layer 4 of the window mixin chain (after ``FindMixin``).
    """

    def toggle_bookmark(self) -> None:
        """Toggle a bookmark on the active page and report the result."""
        viewer = self.tabs.currentWidget()
        if not isinstance(viewer, PDFViewerWidget):
            return
        added = viewer.toggle_bookmark()
        state = "added to" if added else "removed from"
        count = len(viewer.bookmark_pages())
        self.statusBar().showMessage(
            f"Bookmark {state} page {viewer.current_page + 1} ({count} marked, not persisted yet)",
            self.STATUS_TIMEOUT_MS,
        )
