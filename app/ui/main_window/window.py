"""The assembled application window.

``MainWindow`` owns no feature logic of its own: it inherits the mixin chain and
wires the pieces together in ``__init__``. The chain is ordered by dependency,
so each layer may use the layers before it:

1. :class:`~app.ui.main_window.base.WindowBase` - shared state, session, close
2. :class:`~app.ui.main_window.theme.ThemeMixin` - dark mode
3. :class:`~app.ui.main_window.find.FindMixin` - find bar and ``Esc``
4. :class:`~app.ui.main_window.bookmarks.BookmarksMixin` - bookmark toggle
5. :class:`~app.ui.main_window.navigation.NavigationMixin` - page bar, zoom
6. :class:`~app.ui.main_window.documents.DocumentsMixin` - tab lifecycle
7. :class:`~app.ui.main_window.sidebar.SidebarMixin` - sidebar and splitter
8. :class:`~app.ui.main_window.commands.CommandsMixin` - menus and palette

Only this class is instantiated; the mixins exist to be mixed in.
"""

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget

from app.core.session import SessionManager
from app.ui.document_tabs import DocumentTabBar, TabOverflowButton
from app.ui.main_window.commands import CommandsMixin


class MainWindow(CommandsMixin):
    """Main application window: session restore, tab widget, and feature mixins."""

    def __init__(self, documents: Sequence[Path] = ()) -> None:
        """Build the window, then open the requested, remembered, or sample documents.

        ``documents`` holds the PDFs named on the command line. Opening them takes
        precedence over the saved session because the caller asked for them
        explicitly; with none, the window restores the session and falls back to
        the sample PDFs of a source checkout.
        """
        super().__init__()
        self.setWindowTitle("Fallow PDF Reader")
        self.session_manager = SessionManager()
        session = self.session_manager.load()
        self.dark_mode = session["dark_mode"] if session else True
        # Settings first, because they say where the library lives; then the
        # library itself, because the sidebar reads bookmarks and notes from it.
        # ``create_storage`` is allowed to fall back to a temporary library, so
        # it never aborts the launch.
        self.create_settings()
        self.create_storage()
        # app/ui/main_window/window.py -> repository root, where the sample PDFs
        # live when the application runs from a source checkout.
        repository_root = Path(__file__).resolve().parents[3]
        self.tabs = QTabWidget()
        self.tabs.setTabBar(DocumentTabBar(self.tabs))
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.refresh_tab_window)
        self.tabs.currentChanged.connect(self.update_page_controls)
        self.overflow_button = TabOverflowButton(self.tab_entries, self)
        self.overflow_button.document_selected.connect(self.focus_tab)
        self.tabs.setCornerWidget(self.overflow_button, Qt.Corner.TopRightCorner)
        self.create_sidebar()
        self.create_menu_bar()
        self.create_bottom_bar()
        self.create_find_bar()
        self.create_shortcuts()

        if documents:
            # A document named on the command line is an explicit request, so it
            # wins over both the saved session and the bundled samples.
            for document in documents:
                self.add_pdf(document, self.tab_title(document))
            self.tabs.setCurrentIndex(0)
        elif session and session["tabs"]:
            for tab in session["tabs"]:
                self.add_pdf(Path(tab["file_path"]), self.tab_title(Path(tab["file_path"])), tab["current_page"])
            self.tabs.setCurrentIndex(session["active_tab_index"])
        else:
            self.add_sample_documents(repository_root)
        self.update_tab_bar_visibility()
        self.refresh_tab_window(self.tabs.currentIndex())
        self.dark_mode_action.setChecked(self.dark_mode)
        self.apply_theme()
        self.showMaximized()
