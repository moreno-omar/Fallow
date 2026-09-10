"""Application entrypoint for the Fallow PDF reader."""

import sys

from PySide6.QtWidgets import QApplication, QMainWindow


class MainWindow(QMainWindow):
    """Initial application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fallow PDF Reader")
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