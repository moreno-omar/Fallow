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
7. :class:`~app.ui.main_window.commands.CommandsMixin` - menus and palette

Only this class is instantiated; the mixins exist to be mixed in.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget

from app.core.session import SessionManager
from app.ui.document_tabs import DocumentTabBar, TabOverflowButton
from app.ui.main_window.commands import CommandsMixin


class MainWindow(CommandsMixin):
    """Main application window: session restore, tab widget, and feature mixins."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fallow PDF Reader")
        self.session_manager = SessionManager()
        session = self.session_manager.load()
        self.dark_mode = session["dark_mode"] if session else True
        # app/ui/main_window/window.py -> repository root, where the sample PDFs live.
        repository_root = Path(__file__).resolve().parents[3]
        self.tabs = QTabWidget()
        self.tabs.setTabBar(DocumentTabBar(self.tabs))
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.refresh_tab_window)
        self.tabs.currentChanged.connect(self.update_page_controls)
        self.setCentralWidget(self.tabs)
        self.overflow_button = TabOverflowButton(self.tab_entries, self)
        self.overflow_button.document_selected.connect(self.focus_tab)
        self.tabs.setCornerWidget(self.overflow_button, Qt.Corner.TopRightCorner)
        self.create_menu_bar()
        self.create_bottom_bar()
        self.create_find_bar()
        self.create_shortcuts()

        if session and session["tabs"]:
            for tab in session["tabs"]:
                self.add_pdf(Path(tab["file_path"]), self.tab_title(Path(tab["file_path"])), tab["current_page"])
            self.tabs.setCurrentIndex(session["active_tab_index"])
        else:
            self.add_pdf(repository_root / "alices-adventures-in-wonderland.pdf", "Alice")
            self.add_pdf(repository_root / "frankenstein.pdf", "Frankenstein")
        self.update_tab_bar_visibility()
        self.refresh_tab_window(self.tabs.currentIndex())
        self.dark_mode_action.setChecked(self.dark_mode)
        self.apply_theme()
        self.showMaximized()
