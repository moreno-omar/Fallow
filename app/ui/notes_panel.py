"""Left-hand notes panel.

Phase 12 only builds the container and the splitter that holds it: the panel is a
header plus an empty state, and it carries no note data of its own. The Markdown
editor and the per-document note store belong to Phase 13, which fills this
widget in rather than adding a second panel next to it.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class NotesPanel(QWidget):
    """The pane that shows the notes of the active document.

    The panel is deliberately empty for now; it exists so the window can give the
    reader a resizable left column that Phase 13 can fill with an editor.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the panel header and its empty-state label."""
        super().__init__(parent)
        self.setObjectName("notesPanel")
        # A plain QWidget paints a stylesheet background only when this
        # attribute is set, which the dark theme relies on.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        header = QLabel("Notes")
        header.setObjectName("notesHeader")

        self.placeholder = QLabel("No notes for this document yet.")
        self.placeholder.setObjectName("notesPlaceholder")
        self.placeholder.setWordWrap(True)
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(header)
        # Stretch keeps the placeholder at the top instead of centring it.
        layout.addWidget(self.placeholder, 1)
