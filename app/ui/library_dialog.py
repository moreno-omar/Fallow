"""Pick where the library -- ``library.db`` and the notes tree -- is stored.

The default is the XDG data directory, which is not writable on every machine: a
read-only home, a locked-down desktop, a full disk. The window degrades to a
temporary library when the configured folder cannot be used (see
:func:`app.core.database.open_library`) and offers this dialog so the reader can
point the app at a folder that does work.

Switching the folder does not copy anything: the chosen location shows its own
notes and marks, which the dialog says plainly so the change is never a surprise.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.database import default_data_root


class LibraryLocationDialog(QDialog):
    """Choose the folder that holds the library, or return to the default.

    ``selected_root`` is the choice to apply: a path, or ``None`` for the platform
    default. It is initialised to the stored choice, so the caller can tell an
    unchanged dialog from a real switch by comparing it with what was stored.
    """

    def __init__(
        self,
        active_root: Path,
        configured_root: Path | None,
        temporary: bool,
        dark_mode: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Describe the active location and start from the configured choice."""
        super().__init__(parent)
        self.setWindowTitle("Library Location")
        self.setStyleSheet(self._stylesheet(dark_mode))
        self.setModal(True)
        self.selected_root: Path | None = configured_root

        intro = QLabel(
            "Notes and bookmarks live in a folder of their own, not inside the PDFs. "
            "Choosing a different folder shows a different set of notes and marks: "
            "nothing is copied."
        )
        intro.setWordWrap(True)

        self.location_label = QLabel()
        self.location_label.setWordWrap(True)
        self.warning_label = QLabel(
            "Notes and bookmarks could not be saved in the configured location, so this "
            f"session is running in temporary mode ({active_root}) and will forget them "
            "when it closes."
        )
        self.warning_label.setObjectName("libraryWarning")
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(temporary)

        choose_button = QPushButton("Choose Folder…")
        choose_button.clicked.connect(self.choose_folder)
        default_button = QPushButton("Use Default Location")
        default_button.clicked.connect(self.use_default_location)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        actions = QHBoxLayout()
        actions.addWidget(choose_button)
        actions.addWidget(default_button)
        actions.addStretch(1)
        actions.addWidget(buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(intro)
        layout.addWidget(self.location_label)
        layout.addWidget(self.warning_label)
        layout.addLayout(actions)

        self.update_location_label()

    # -- selection -----------------------------------------------------------------

    def choose_folder(self) -> None:
        """Ask for a folder and remember it as the choice."""
        start = str(self.selected_root or default_data_root())
        folder = QFileDialog.getExistingDirectory(self, "Choose Library Folder", start)
        if not folder:
            return
        self.selected_root = Path(folder)
        self.update_location_label()

    def use_default_location(self) -> None:
        """Forget the override and go back to the platform data directory."""
        self.selected_root = None
        self.update_location_label()

    def update_location_label(self) -> None:
        """Show the folder the library will use if this dialog is accepted."""
        target = self.selected_root if self.selected_root is not None else default_data_root()
        suffix = "" if self.selected_root is not None else " (default)"
        self.location_label.setText(f"<b>Library folder:</b> {target}{suffix}")

    @staticmethod
    def _stylesheet(dark_mode: bool) -> str:
        """Return the dialog styling for the active application theme."""
        if dark_mode:
            background, surface, border, text = "#2E3440", "#3B4252", "#4C566A", "#ECEFF4"
            accent, hint = "#5E81AC", "#EBCB8B"
        else:
            background, surface, border, text = "#F7F7F9", "#FFFFFF", "#C9CDD4", "#1F2430"
            accent, hint = "#3B6FD4", "#8B5A00"
        return (
            f"QDialog {{ background: {background}; }}"
            f"QLabel {{ color: {text}; }}"
            f"QLabel#libraryWarning {{ color: {hint}; }}"
            f"QPushButton {{ background: {surface}; color: {text};"
            f" border: 1px solid {border}; padding: 5px 10px; }}"
            f"QPushButton:hover {{ background: {accent}; color: #ECEFF4; }}"
        )
