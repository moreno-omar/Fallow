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

Storage belongs to this layer because it is lifecycle, not a feature: the library
is opened before any feature layer exists, and opening it is allowed to fail.
"""

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget

from app.core.database import Database, open_library
from app.core.session import SessionManager
from app.ui.document_tabs import TabOverflowButton


class WindowBase(QMainWindow):
    """Session persistence plus the state shared by every feature mixin."""

    # How long transient status-bar messages stay visible.
    STATUS_TIMEOUT_MS = 3000

    # Application scope for ``QSettings``. On Linux this lands in
    # ``$XDG_CONFIG_HOME/linux-pdf-reader``, the same folder as ``session.json``,
    # so the app keeps one config folder instead of two.
    SETTINGS_ORGANIZATION = "linux-pdf-reader"
    SETTINGS_APPLICATION = "Fallow PDF Reader"
    # A reader-chosen library folder; absent means the XDG data directory.
    STORAGE_SETTING_KEY = "storage/data_root"

    # Assigned by ``MainWindow.__init__``. Declared here so each layer and the
    # type checker see the window's shared state.
    session_manager: SessionManager
    settings: QSettings
    database: Database
    storage_notice: QLabel
    tabs: QTabWidget
    overflow_button: TabOverflowButton
    dark_mode: bool
    dark_mode_action: QAction
    palette_action: QAction

    # -- settings ------------------------------------------------------------------

    def create_settings(self) -> None:
        """Create the one ``QSettings`` store every layer reads and writes."""
        self.settings = QSettings(self.SETTINGS_ORGANIZATION, self.SETTINGS_APPLICATION)

    def configured_data_root(self) -> Path | None:
        """Return the library folder the reader chose, or ``None`` for the default."""
        stored = self.settings.value(self.STORAGE_SETTING_KEY)
        if isinstance(stored, str) and stored.strip():
            return Path(stored).expanduser()
        return None

    @staticmethod
    def setting_bool(value: object, default: bool) -> bool:
        """Interpret a stored setting as a boolean.

        ``QSettings.value(key, default, bool)`` cannot be used for this: Qt
        converts through ``QVariant.toBool``, where every non-empty *string* is
        true, so a stored ``"false"`` would come back as ``True``. Reading
        untyped and converting here keeps ``False`` meaning ``False``.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on")
        if isinstance(value, int):
            return value != 0
        return default

    @staticmethod
    def setting_int(value: object, default: int) -> int:
        """Interpret a stored setting as an integer, falling back when it is not one."""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    # -- storage -------------------------------------------------------------------

    def create_storage(self) -> None:
        """Open the library and report when it had to fall back to a temporary one."""
        self.storage_notice = QLabel()
        self.storage_notice.setObjectName("storageNotice")
        notice_font = self.storage_notice.font()
        notice_font.setBold(True)
        self.storage_notice.setFont(notice_font)
        self.storage_notice.setVisible(False)
        # A permanent widget rather than ``showMessage``: the transient status
        # messages (zoom, bookmark added) would clear a message shown that way
        # after a few seconds, and this warning is not transient.
        self.statusBar().addPermanentWidget(self.storage_notice)
        self.database, notice = open_library(self.configured_data_root())
        self.set_storage_notice(notice)

    def set_storage_notice(self, notice: str | None) -> None:
        """Show or clear the non-blocking degraded-storage indicator."""
        self.storage_notice.setVisible(notice is not None)
        if notice is None:
            self.storage_notice.clear()
            self.storage_notice.setToolTip("")
            return
        self.storage_notice.setText(f"⚠ {notice}")
        reason = self.database.temporary_reason
        self.storage_notice.setToolTip(
            f"{notice}\n{reason or ''}\n"
            "File ▸ Library Location… lets you choose a folder that can be written."
        )

    def switch_library(self, data_root: Path | None) -> None:
        """Re-open the library at ``data_root``, or at the default when ``None``.

        The chosen folder is stored even when it turns out to be unusable: it is a
        preference, so the next launch should try it again rather than silently
        forgetting what the reader asked for.
        """
        if data_root is None:
            self.settings.remove(self.STORAGE_SETTING_KEY)
        else:
            self.settings.setValue(self.STORAGE_SETTING_KEY, str(data_root))
        self.settings.sync()
        self.database, notice = open_library(data_root)
        self.set_storage_notice(notice)

    # -- session -------------------------------------------------------------------

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
