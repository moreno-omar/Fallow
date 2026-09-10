"""Application entrypoint for the Fallow PDF reader."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow

from app.ui.viewer_tab import PDFViewerWidget


class MainWindow(QMainWindow):
    """Initial application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fallow PDF Reader")
        pdf_path = Path(__file__).resolve().parents[1] / "alices-adventures-in-wonderland.pdf"
        self.viewer = PDFViewerWidget(pdf_path)
        self.setCentralWidget(self.viewer)
        self.showMaximized()


def main() -> int:
    """Create and run the application window."""
    application = QApplication(sys.argv)

    # needed to actually make window visible
    window = MainWindow()
    window.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(main())