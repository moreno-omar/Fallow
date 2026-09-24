"""Application entrypoint for the Fallow PDF reader."""

import sys
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIntValidator, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QSizePolicy,
    QTabWidget,
    QToolBar,
    QWidget,
)

from app.core.session import SessionManager
from app.ui.command_palette import Command, CommandPalette
from app.ui.document_tabs import DocumentTabBar, TabEntry, TabOverflowButton, TabSearchDialog
from app.ui.viewer_tab import PDFViewerWidget


class MainWindow(QMainWindow):
    """Initial application window."""

    STATUS_TIMEOUT_MS = 3000
    TAB_SEARCH_SHORTCUT = "Ctrl+Shift+A"
    DARK_MODE_SHORTCUTS = ("Ctrl+Shift+D", "Alt+D", "Ctrl+D")
    # "Ctrl++" needs Shift on many layouts, so the plain '=' binding is listed
    # too. Every entry must be unique: Qt drops shortcuts that are registered
    # twice for one action as an ambiguous overload.
    ZOOM_IN_SHORTCUTS = ("Ctrl++", "Ctrl+=")
    ZOOM_OUT_SHORTCUTS = ("Ctrl+-",)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fallow PDF Reader")
        self.session_manager = SessionManager()
        session = self.session_manager.load()
        self.dark_mode = session["dark_mode"] if session else True
        repository_root = Path(__file__).resolve().parents[1]
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

    def create_bottom_bar(self) -> None:
        """Create centered page navigation controls in a bottom toolbar."""
        self.bottom_bar = QToolBar("Page Navigation", self)
        self.bottom_bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.bottom_bar)

        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.page_input = QLineEdit()
        self.page_input.setPlaceholderText("Page")
        self.page_input.setMaximumWidth(90)
        self.page_input.setValidator(QIntValidator(1, 1, self.page_input))
        self.page_input.returnPressed.connect(self.go_to_page)

        self.page_status = QLabel()
        self.bottom_bar.addWidget(left_spacer)
        self.bottom_bar.addWidget(self.page_input)
        self.bottom_bar.addWidget(self.page_status)
        self.bottom_bar.addWidget(right_spacer)

    def create_find_bar(self) -> None:
        """Create the hidden top toolbar that hosts document search."""
        self.find_bar = QToolBar("Find", self)
        self.find_bar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.find_bar)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find in document")
        self.find_input.setMinimumWidth(240)
        self.find_input.returnPressed.connect(self.find_next)

        self.find_status = QLabel()
        self.find_bar.addWidget(self.find_input)
        self.find_bar.addWidget(self.find_status)
        self.find_bar.setVisible(False)

    def create_shortcuts(self) -> None:
        """Register window-level shortcuts that are not part of a menu action."""
        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.escape_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.escape_shortcut.activated.connect(self.hide_find_bar)

    def connect_viewer(self, viewer: PDFViewerWidget) -> None:
        """Connect one viewer's page and zoom state to the window controls."""
        viewer.page_changed.connect(self.update_page_status)
        viewer.zoom_changed.connect(self.show_zoom)

    def update_page_controls(self, tab_index: int) -> None:
        """Refresh page controls when the active document changes."""
        if tab_index < 0:
            self.page_input.clear()
            self.page_status.clear()
            return
        viewer = self.tabs.widget(tab_index)
        if isinstance(viewer, PDFViewerWidget):
            self.update_page_status(viewer.current_page, viewer.engine.page_count)

    def update_page_status(self, current_page: int, page_count: int) -> None:
        """Display the active page as a one-based position and total."""
        self.page_input.setText(str(current_page + 1))
        self.page_status.setText(f"of {page_count}")
        self.page_input.setValidator(QIntValidator(1, page_count, self.page_input))

    def go_to_page(self) -> None:
        """Navigate the active tab to the page entered by the user."""
        viewer = self.tabs.currentWidget()
        if not isinstance(viewer, PDFViewerWidget):
            return
        page_number = self.page_input.text().strip()
        if page_number:
            viewer.set_page(int(page_number) - 1)

    def show_find_bar(self) -> None:
        """Reveal the find bar and focus its query field."""
        if self.tabs.count() == 0:
            return
        self.find_bar.setVisible(True)
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find_bar(self) -> None:
        """Hide the find bar and remove every match highlight."""
        if not self.find_bar.isVisible():
            return
        self.find_bar.setVisible(False)
        self.find_input.clear()
        self.find_status.clear()
        viewer = self.tabs.currentWidget()
        if isinstance(viewer, PDFViewerWidget):
            viewer.clear_find()
            viewer.focus_canvas()

    def find_next(self) -> None:
        """Search the active document for the text in the find field."""
        viewer = self.tabs.currentWidget()
        if not isinstance(viewer, PDFViewerWidget):
            return
        query = self.find_input.text().strip()
        if not query:
            viewer.clear_find()
            self.find_status.clear()
            return
        matches = viewer.find(query)
        if matches:
            label = "match" if matches == 1 else "matches"
            self.find_status.setText(f"{matches} {label} on page {viewer.current_page + 1}")
        else:
            self.find_status.setText("No matches")

    def focus_page_input(self) -> None:
        """Focus the page-number field so a destination can be typed."""
        if self.tabs.count() == 0:
            return
        self.page_input.setFocus()
        self.page_input.selectAll()

    def close_current_tab(self) -> None:
        """Close the active document tab while keeping the window open."""
        tab_index = self.tabs.currentIndex()
        if tab_index >= 0:
            self.close_tab(tab_index)
            viewer = self.tabs.currentWidget()
            if isinstance(viewer, PDFViewerWidget):
                viewer.focus_canvas()

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

    def zoom_in(self) -> None:
        """Magnify the active document by one zoom step."""
        viewer = self.tabs.currentWidget()
        if isinstance(viewer, PDFViewerWidget):
            viewer.zoom_in()

    def zoom_out(self) -> None:
        """Shrink the active document by one zoom step."""
        viewer = self.tabs.currentWidget()
        if isinstance(viewer, PDFViewerWidget):
            viewer.zoom_out()

    def reset_zoom(self) -> None:
        """Restore fit-to-page magnification for the active document."""
        viewer = self.tabs.currentWidget()
        if isinstance(viewer, PDFViewerWidget):
            viewer.reset_zoom()

    def show_zoom(self, zoom: float) -> None:
        """Report the current magnification in the status bar."""
        self.statusBar().showMessage(f"Zoom {zoom * 100:.0f}%", self.STATUS_TIMEOUT_MS)

    def quit_application(self) -> None:
        """Close the window, which saves the session on the way out."""
        self.close()

    def current_viewer(self) -> PDFViewerWidget | None:
        """Return the active document viewer, or ``None`` when no document is open."""
        viewer = self.tabs.currentWidget()
        return viewer if isinstance(viewer, PDFViewerWidget) else None

    def next_page(self) -> None:
        """Advance the active document by one page."""
        viewer = self.current_viewer()
        if viewer is not None:
            viewer.next_page()

    def previous_page(self) -> None:
        """Move the active document back by one page."""
        viewer = self.current_viewer()
        if viewer is not None:
            viewer.previous_page()

    def show_command_palette(self) -> None:
        """Open the searchable command palette and run the command it returns.

        The command runs only after ``exec()`` returns, so a handler that opens
        its own dialog (for example ``Open``) is never nested inside the
        palette's modal event loop.
        """
        palette = CommandPalette(self.collect_commands(), self.dark_mode, self)
        if palette.exec() == QDialog.DialogCode.Accepted and palette.selected_command is not None:
            palette.selected_command.handler()

    def show_tab_search(self) -> None:
        """List the open documents and focus the tab the user chooses.

        Like the command palette, the tab is activated only after ``exec()``
        returns, so no tab is closed or re-indexed while the modal list is open.
        """
        commands = self.tab_commands()
        if not commands:
            return
        dialog = TabSearchDialog(commands, self.dark_mode, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_command is not None:
            dialog.selected_command.handler()

    def tab_commands(self) -> list[Command]:
        """Build one palette entry per open document, each focusing its tab."""
        return [
            Command(entry.title, entry.hint, partial(self.focus_tab, entry.index))
            for entry in self.tab_entries()
        ]

    def tab_entries(self) -> list[TabEntry]:
        """Describe every open document for the overflow menu and Tab Search.

        Called on demand rather than cached, so the list is always in step with
        the tab widget even while tabs are being added or closed.
        """
        active_index = self.tabs.currentIndex()
        entries: list[TabEntry] = []
        for index in range(self.tabs.count()):
            viewer = self.tabs.widget(index)
            if not isinstance(viewer, PDFViewerWidget):
                continue
            entries.append(
                TabEntry(
                    index=index,
                    title=self.tabs.tabText(index),
                    location=str(viewer.engine.file_path),
                    page=viewer.current_page,
                    page_count=viewer.engine.page_count,
                    active=index == active_index,
                )
            )
        return entries

    def focus_tab(self, tab_index: int) -> None:
        """Activate one open document and hand keyboard focus back to the page."""
        if not 0 <= tab_index < self.tabs.count():
            return
        # Slide the visible window onto the target first, so ``setCurrentIndex``
        # never has to activate a tab the bar is currently hiding.
        self.tabs.tabBar().sync_visible_window(tab_index)
        self.tabs.setCurrentIndex(tab_index)
        viewer = self.current_viewer()
        if viewer is not None:
            viewer.focus_canvas()

    def refresh_tab_window(self, tab_index: int) -> None:
        """Keep the active tab inside the tab bar's five-tab visible window."""
        self.tabs.tabBar().sync_visible_window(tab_index)

    def collect_commands(self) -> list[Command]:
        """Build every palette entry from menu actions and viewer-level keys."""
        commands = [self.action_command(action) for action in self.menu_actions()]
        commands.extend(self.viewer_commands())
        return commands

    def menu_actions(self) -> list[QAction]:
        """Return the actionable menu entries, excluding the palette itself."""
        actions: list[QAction] = []
        for menu_action in self.menuBar().actions():
            menu = menu_action.menu()
            if menu is None:
                continue
            for action in menu.actions():
                if action.isSeparator() or action is self.palette_action:
                    continue
                actions.append(action)
        return actions

    @staticmethod
    def action_command(action: QAction) -> Command:
        """Convert a shortcut action into a palette command."""
        labels = [sequence.toString(QKeySequence.SequenceFormat.NativeText) for sequence in action.shortcuts()]
        shortcut = ", ".join(label for label in labels if label)
        return Command(action.text().replace("&", ""), shortcut, action.trigger)

    def viewer_commands(self) -> list[Command]:
        """Return commands for the keys the active viewer handles itself.

        Page turning lives in ``PDFViewerWidget`` as per-widget ``QShortcut``s,
        so these entries are not visible in the menu bar and must be added here
        for the palette to advertise them.
        """
        return [
            Command("Next Page", "Right / Down / Page Down", self.next_page),
            Command("Previous Page", "Left / Up / Page Up", self.previous_page),
        ]

    def create_action(self, title: str, shortcut: str, handler) -> QAction:
        """Create a window action with an optional single shortcut."""
        action = QAction(title, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(handler)
        return action

    def create_menu_bar(self) -> None:
        """Create the application menus and connect every shortcut action."""
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.create_open_action())
        file_menu.addAction(self.create_action("Close Tab", "Ctrl+W", self.close_current_tab))
        file_menu.addSeparator()
        file_menu.addAction(self.create_action("Quit", "Ctrl+Q", self.quit_application))

        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction(self.create_action("Find", "Ctrl+F", self.show_find_bar))
        edit_menu.addAction(self.create_action("Go to Page", "Ctrl+G", self.focus_page_input))
        edit_menu.addAction(self.create_action("Bookmark Page", "Ctrl+B", self.toggle_bookmark))

        view_menu = self.menuBar().addMenu("View")
        self.palette_action = self.create_action("Command Palette", "Ctrl+P", self.show_command_palette)
        view_menu.addAction(self.palette_action)
        view_menu.addAction(self.create_action("Tab Search", self.TAB_SEARCH_SHORTCUT, self.show_tab_search))
        view_menu.addSeparator()
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setShortcuts([QKeySequence(key) for key in self.DARK_MODE_SHORTCUTS])
        self.dark_mode_action.toggled.connect(self.set_dark_mode)
        view_menu.addAction(self.dark_mode_action)
        view_menu.addSeparator()
        view_menu.addAction(self.create_zoom_in_action())
        view_menu.addAction(self.create_zoom_out_action())
        view_menu.addAction(self.create_action("Reset Zoom", "Ctrl+0", self.reset_zoom))
        self.menuBar().addMenu("Help")

    def create_zoom_in_action(self) -> QAction:
        """Create the magnification action with its shortcut variants."""
        zoom_in_action = self.create_action("Zoom In", "", self.zoom_in)
        zoom_in_action.setShortcuts([QKeySequence(key) for key in self.ZOOM_IN_SHORTCUTS])
        return zoom_in_action

    def create_zoom_out_action(self) -> QAction:
        """Create the shrink action with its shortcut."""
        zoom_out_action = self.create_action("Zoom Out", "", self.zoom_out)
        zoom_out_action.setShortcuts([QKeySequence(key) for key in self.ZOOM_OUT_SHORTCUTS])
        return zoom_out_action

    def set_dark_mode(self, enabled: bool) -> None:
        """Apply the selected UI and PDF canvas theme."""
        self.dark_mode = enabled
        self.apply_theme()
        for index in range(self.tabs.count()):
            viewer = self.tabs.widget(index)
            if isinstance(viewer, PDFViewerWidget):
                viewer.set_dark_mode(enabled)
        self.save_session()

    def apply_theme(self) -> None:
        """Apply neutral dark or default widget styling."""
        if self.dark_mode:
            self.setStyleSheet(
                "QMainWindow, QTabWidget, QTabBar, QToolBar { background: #2E3440; color: #ECEFF4; }"
                "QScrollArea, QScrollArea > QWidget > QWidget { background: #2E3440; }"
                "QLabel, QLineEdit, QMenuBar, QMenu, QStatusBar { color: #ECEFF4; }"
                "QMenuBar::item:selected, QMenu::item:selected { background: #4C566A; }"
                "QLineEdit { background: #3B4252; border: 1px solid #81A1C1; }"
                # Menus and the tab overflow button need explicit backgrounds,
                # otherwise the styled text colour lands on a light default.
                "QMenu { background: #3B4252; border: 1px solid #4C566A; }"
                "QMenu::item { padding: 4px 20px 4px 8px; }"
                "QToolButton { background: #3B4252; color: #ECEFF4; border: 1px solid #4C566A; }"
                "QToolButton:hover { background: #4C566A; }"
                "QToolButton::menu-indicator { image: none; }"
            )
        else:
            self.setStyleSheet("")

    def create_open_action(self) -> QAction:
        """Create the action that opens a PDF file picker."""
        open_action = QAction("Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_pdf_dialog)
        return open_action

    def open_pdf_dialog(self) -> None:
        """Open a selected PDF in a new tab."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            str(Path.home()),
            "PDF files (*.pdf);;All files (*)",
        )
        if not file_name:
            return

        file_path = Path(file_name).resolve()
        if file_path.suffix.lower() != ".pdf" or not file_path.is_file():
            return
        self.add_pdf(file_path, self.tab_title(file_path))
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        self.update_tab_bar_visibility()
        self.save_session()

    def add_pdf(self, file_path: Path, title: str, current_page: int = 0) -> None:
        """Add a PDF viewer as a new document tab."""
        viewer = PDFViewerWidget(file_path, self.dark_mode)
        viewer.current_page = min(current_page, viewer.engine.page_count - 1)
        self.connect_viewer(viewer)
        self.tabs.addTab(viewer, title)
        # Titles are elided to fit the tab width, so the tooltip carries the full
        # document name (the absolute path also tells apart equal file names).
        self.refresh_tab_window(self.tabs.currentIndex())
        self.tabs.setTabToolTip(self.tabs.count() - 1, str(file_path))
        if self.tabs.currentWidget() is viewer:
            self.update_page_controls(self.tabs.currentIndex())

    @staticmethod
    def tab_title(file_path: Path) -> str:
        """Create a readable tab title from a PDF filename."""
        return file_path.stem.replace("-", " ").title()

    def close_tab(self, tab_index: int) -> None:
        """Close one document tab while keeping the application open."""
        viewer = self.tabs.widget(tab_index)
        self.tabs.removeTab(tab_index)
        if viewer is not None:
            viewer.dispose()
            viewer.deleteLater()
        if self.tabs.count() == 0:
            self.find_bar.setVisible(False)
            self.find_input.clear()
            self.find_status.clear()
        self.update_tab_bar_visibility()
        self.refresh_tab_window(self.tabs.currentIndex())
        self.save_session()

    def update_tab_bar_visibility(self) -> None:
        """Show the tab strip only when more than one document is open."""
        has_tab_strip = self.tabs.count() > 1
        self.tabs.tabBar().setVisible(has_tab_strip)
        self.overflow_button.setVisible(has_tab_strip)

    def save_session(self) -> None:
        """Save the current tabs and active document position."""
        viewers = [self.tabs.widget(index) for index in range(self.tabs.count())]
        self.session_manager.save(self.tabs.currentIndex(), viewers, self.dark_mode)

    def closeEvent(self, event) -> None:
        self.save_session()
        for index in range(self.tabs.count()):
            viewer = self.tabs.widget(index)
            if viewer is not None:
                viewer.dispose()
        super().closeEvent(event)


def main() -> int:
    """Create and run the application window."""
    application = QApplication(sys.argv)

    # needed to actually make window visible
    window = MainWindow()
    window.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(main())