"""Application entrypoint for the Fallow PDF reader."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
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
from app.ui.viewer_tab import PDFViewerWidget


class MainWindow(QMainWindow):
    """Initial application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fallow PDF Reader")
        self.session_manager = SessionManager()
        session = self.session_manager.load()
        self.dark_mode = session["dark_mode"] if session else True
        repository_root = Path(__file__).resolve().parents[1]
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.update_page_controls)
        self.setCentralWidget(self.tabs)
        self.create_menu_bar()
        self.create_bottom_bar()

        if session and session["tabs"]:
            for tab in session["tabs"]:
                self.add_pdf(Path(tab["file_path"]), self.tab_title(Path(tab["file_path"])), tab["current_page"])
            self.tabs.setCurrentIndex(session["active_tab_index"])
        else:
            self.add_pdf(repository_root / "alices-adventures-in-wonderland.pdf", "Alice")
            self.add_pdf(repository_root / "frankenstein.pdf", "Frankenstein")
        self.update_tab_bar_visibility()
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

    def connect_viewer(self, viewer: PDFViewerWidget) -> None:
        """Connect one viewer's page state to the bottom-bar controls."""
        viewer.page_changed.connect(self.update_page_status)

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

    def create_menu_bar(self) -> None:
        """Create the application menus and connect the PDF open action."""
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.create_open_action())
        view_menu = self.menuBar().addMenu("View")
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.toggled.connect(self.set_dark_mode)
        view_menu.addAction(self.dark_mode_action)
        self.menuBar().addMenu("Help")

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
                "QLabel, QLineEdit, QMenuBar, QMenu { color: #ECEFF4; }"
                "QMenuBar::item:selected, QMenu::item:selected { background: #4C566A; }"
                "QLineEdit { background: #3B4252; border: 1px solid #81A1C1; }"
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
        self.update_tab_bar_visibility()
        self.save_session()

    def update_tab_bar_visibility(self) -> None:
        """Show the tab bar only when more than one document is open."""
        self.tabs.tabBar().setVisible(self.tabs.count() > 1)

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