"""Application entrypoint for the Fallow PDF reader.

All window behaviour lives in :mod:`app.ui.main_window`; this module only creates
the ``QApplication``, opens the window, and hands control to the Qt event loop.
"""

import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def main() -> int:
    """Create the application, show the main window, and run the event loop."""
    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
