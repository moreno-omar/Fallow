"""Application entrypoint for the Fallow PDF reader."""

import sys
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QTabWidget

from app.core.session import SessionManager
from app.ui.viewer_tab import PDFViewerWidget


class MainWindow(QMainWindow):
    """Initial application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fallow PDF Reader")
        self.session_manager = SessionManager()
        repository_root = Path(__file__).resolve().parents[1]
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)
        self.create_menu_bar()

        session = self.session_manager.load()
        if session and session["tabs"]:
            for tab in session["tabs"]:
                self.add_pdf(Path(tab["file_path"]), self.tab_title(Path(tab["file_path"])), tab["current_page"])
            self.tabs.setCurrentIndex(session["active_tab_index"])
        else:
            self.add_pdf(repository_root / "alices-adventures-in-wonderland.pdf", "Alice")
            self.add_pdf(repository_root / "frankenstein.pdf", "Frankenstein")
        self.update_tab_bar_visibility()
        self.showMaximized()

    def create_menu_bar(self) -> None:
        """Create the application menus and connect the PDF open action."""
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.create_open_action())
        self.menuBar().addMenu("View")
        self.menuBar().addMenu("Help")

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
        viewer = PDFViewerWidget(file_path)
        viewer.current_page = min(current_page, viewer.engine.page_count - 1)
        self.tabs.addTab(viewer, title)

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
        self.session_manager.save(self.tabs.currentIndex(), viewers)

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