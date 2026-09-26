"""Document lifecycle: opening files, closing tabs, and list-switching tabs.

``add_pdf`` stays the only place that turns a path into a tab, so a restored
document, a file-picker choice, and a future drag-and-drop all get the same
rendering, navigation, and session behaviour.
"""

from functools import partial
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QFileDialog

from app.ui.command_palette import Command
from app.ui.document_tabs import TabEntry, TabSearchDialog
from app.ui.main_window.navigation import NavigationMixin
from app.ui.viewer_tab import PDFViewerWidget


class DocumentsMixin(NavigationMixin):
    """Create, close, and switch document tabs, including Tab Search.

    Layer 6 of the window mixin chain (after ``NavigationMixin``).
    """

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

    def close_current_tab(self) -> None:
        """Close the active document tab while keeping the window open."""
        tab_index = self.tabs.currentIndex()
        if tab_index >= 0:
            self.close_tab(tab_index)
            viewer = self.current_viewer()
            if viewer is not None:
                viewer.focus_canvas()

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

    def tab_commands(self) -> list[Command]:
        """Build one palette entry per open document, each focusing its tab."""
        return [
            Command(entry.title, entry.hint, partial(self.focus_tab, entry.index))
            for entry in self.tab_entries()
        ]

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
