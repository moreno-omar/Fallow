"""Application entrypoint for the Fallow PDF reader."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from app.ui.viewer_tab import PDFViewerWidget


class MainWindow(QMainWindow):
    """Initial application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fallow PDF Reader")
        repository_root = Path(__file__).resolve().parents[1]
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        self.add_pdf(repository_root / "alices-adventures-in-wonderland.pdf", "Alice")
        self.add_pdf(repository_root / "frankenstein.pdf", "Frankenstein")
        self.update_tab_bar_visibility()
        self.showMaximized()

    def add_pdf(self, file_path: Path, title: str) -> None:
        """Add a PDF viewer as a new document tab."""
        viewer = PDFViewerWidget(file_path)
        self.tabs.addTab(viewer, title)

    def close_tab(self, tab_index: int) -> None:
        """Close one document tab while keeping the application open."""
        viewer = self.tabs.widget(tab_index)
        self.tabs.removeTab(tab_index)
        if viewer is not None:
            viewer.dispose()
            viewer.deleteLater()
        self.update_tab_bar_visibility()

    def update_tab_bar_visibility(self) -> None:
        """Show the tab bar only when more than one document is open."""
        self.tabs.tabBar().setVisible(self.tabs.count() > 1)


def main() -> int:
    """Create and run the application window."""
    application = QApplication(sys.argv)

    # needed to actually make window visible
    window = MainWindow()
    window.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(main())