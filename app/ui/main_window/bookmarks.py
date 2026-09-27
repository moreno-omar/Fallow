"""Reading marks on the active document.

A bookmark is a page number stored in SQLite against the *content hash* of the
PDF, so marks follow a document when it is renamed or moved and are shared by
two copies of the same file (the identity model the schema is built on). The
panel that displays them lives one layer above, in
:mod:`app.ui.main_window.sidebar`, which is why this layer only writes.
"""

from app.ui.main_window.find import FindMixin
from app.ui.viewer_tab import PDFViewerWidget


class BookmarksMixin(FindMixin):
    """Toggle a bookmark on the current page of the active document.

    Layer 4 of the window mixin chain (after ``FindMixin``). ``self.database`` is
    declared once on ``WindowBase``, so this layer can use it without redeclaring.
    """

    def book_id_for_viewer(self, viewer: PDFViewerWidget) -> int:
        """Return the stored book id for a viewer's document.

        The id is derived from the file's bytes, so it is stable across renames
        and identical for two copies of the same PDF. ``Database.ensure_book``
        caches on path/mtime/size, so the file is hashed once per open document
        rather than once per bookmark toggle.
        """
        return self.database.ensure_book(
            viewer.engine.file_path,
            viewer.engine.title,
            viewer.engine.author,
        )

    def toggle_bookmark(self) -> None:
        """Toggle a bookmark on the active page and report the result."""
        viewer = self.tabs.currentWidget()
        if not isinstance(viewer, PDFViewerWidget):
            return
        book_id = self.book_id_for_viewer(viewer)
        added = self.database.toggle_bookmark(book_id, viewer.current_page)
        state = "added to" if added else "removed from"
        count = self.database.bookmark_count(book_id)
        self.statusBar().showMessage(
            f"Bookmark {state} page {viewer.current_page + 1} ({count} marked)",
            self.STATUS_TIMEOUT_MS,
        )
