"""Shared window state and lifecycle for the ``MainWindow`` mixin stack.

``MainWindow`` is assembled from a stack of small feature mixins instead of
being one large class (see :mod:`app.ui.main_window.window`). Every layer works
on the same handful of widgets and flags, so those are declared once here rather
than repeated -- or left implicit -- in each layer.

The layers form a simple chain, ``WindowBase`` first and ``CommandsMixin`` last,
where each layer may use the ones before it. Two reasons for the chain rather
than independent mixins: ``super()`` stays cooperative, and a later layer can
see the earlier layers' methods, so no layer needs a stub or a ``type: ignore``
to call one. Only ``MainWindow`` is meant to be instantiated.
"""

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QTabWidget

from app.core.session import SessionManager
from app.ui.document_tabs import TabOverflowButton


class WindowBase(QMainWindow):
    """Session persistence plus the state shared by every feature mixin."""

    # How long transient status-bar messages stay visible.
    STATUS_TIMEOUT_MS = 3000

    # Assigned by ``MainWindow.__init__``. Declared here so each layer and the
    # type checker see the window's shared state.
    session_manager: SessionManager
    tabs: QTabWidget
    overflow_button: TabOverflowButton
    dark_mode: bool
    dark_mode_action: QAction
    palette_action: QAction

    def save_session(self) -> None:
        """Save the current tabs and active document position."""
        viewers = [self.tabs.widget(index) for index in range(self.tabs.count())]
        self.session_manager.save(self.tabs.currentIndex(), viewers, self.dark_mode)

    def quit_application(self) -> None:
        """Close the window, which saves the session on the way out."""
        self.close()

    def closeEvent(self, event) -> None:
        """Persist the session, release every document, then close the window."""
        self.save_session()
        for index in range(self.tabs.count()):
            viewer = self.tabs.widget(index)
            if viewer is not None:
                viewer.dispose()
        super().closeEvent(event)
