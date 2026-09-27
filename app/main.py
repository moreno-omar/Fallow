"""Application entrypoint for the Fallow PDF reader.

All window behaviour lives in :mod:`app.ui.main_window`; this module only creates
the ``QApplication``, works out which documents the caller asked for, opens the
window, and hands control to the Qt event loop.
"""

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow


def document_arguments(arguments: Sequence[str]) -> list[Path]:
    """Return the existing PDFs named on the command line.

    A file manager, ``flatpak run``, or an ``AppImage file.pdf`` launch all pass
    the documents to open as arguments, so the application has to read them.
    Anything that is not a readable ``.pdf`` is ignored rather than fatal: a
    desktop environment may hand over options or paths the reader cannot use, and
    that must not stop it from starting.
    """
    documents: list[Path] = []
    for argument in arguments:
        candidate = Path(argument).expanduser()
        if candidate.suffix.lower() == ".pdf" and candidate.is_file():
            documents.append(candidate.resolve())
    return documents


def main() -> int:
    """Create the application, show the main window, and run the event loop."""
    application = QApplication(sys.argv)
    # ``QCoreApplication.arguments()`` has Qt's own options removed already, so
    # ``-platform wayland`` and friends never reach ``document_arguments``.
    window = MainWindow(document_arguments(application.arguments()[1:]))
    window.show()
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
