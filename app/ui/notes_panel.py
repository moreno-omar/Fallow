"""Left-hand notes panel: the note list, the "+" button, and the editor.

Each note is a Markdown file under ``<data_root>/notes/<book-hash>/`` whose
metadata lives in the ``notes`` table (see :mod:`app.core.database`), so the panel
is a thin view: it shows what the storage layer returns and reports the edits it
sees. Saving is debounced, because rewriting a file on every keystroke would be
wasteful, and it is flushed whenever the editor is about to change what it holds.

Markdown *rendering*, tags and a preview belong to Phase 14. The editor here is a
plain text area over those same files, which is enough to create a note and type
in it.
"""

from collections.abc import Sequence

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.database import Note


class NotesPanel(QWidget):
    """List the active document's notes and edit one at a time.

    The panel owns no data: the window hands it the notes of the active document
    and the body to edit, and the panel reports back what the reader did.

    Signals:
        note_requested: a note row was activated; the payload is its id.
        note_created: the "+" button was pressed.
        note_edited: the editor holds a change for a note; the payload is the note
            id and its new Markdown.
    """

    note_requested = Signal(int)
    note_created = Signal()
    note_edited = Signal(int, str)

    # Long enough to coalesce typing, short enough that an edit is never far from
    # being on disk.
    AUTOSAVE_DELAY_MS = 700

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the header, the note list, and the editor."""
        super().__init__(parent)
        self.setObjectName("notesPanel")
        # A plain QWidget paints a stylesheet background only when this
        # attribute is set, which the dark theme relies on.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        header = QLabel("Notes")
        header.setObjectName("notesHeader")
        self.add_button = QToolButton()
        self.add_button.setObjectName("addNoteButton")
        self.add_button.setText("+")
        self.add_button.setToolTip("Create a note for the current page")
        self.add_button.clicked.connect(self.request_new_note)

        header_row = QWidget()
        header_row.setObjectName("notesHeaderRow")
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)
        header_layout.addWidget(header)
        header_layout.addStretch(1)
        header_layout.addWidget(self.add_button)

        self.notes_list = QListWidget()
        self.notes_list.setObjectName("notesList")
        self.notes_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.notes_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # ``itemClicked``/``itemActivated`` fire only for real input, unlike
        # ``currentItemChanged``, which also fires while the list is rebuilt.
        self.notes_list.itemClicked.connect(self.note_clicked)
        self.notes_list.itemActivated.connect(self.note_clicked)

        self.editor = QPlainTextEdit()
        self.editor.setObjectName("noteEditor")
        self.editor.setPlaceholderText("Select a note, or create one with +.")
        self.editor.setReadOnly(True)
        self.editor.textChanged.connect(self.editor_changed)

        self.editor_timer = QTimer(self)
        self.editor_timer.setSingleShot(True)
        self.editor_timer.setInterval(self.AUTOSAVE_DELAY_MS)
        self.editor_timer.timeout.connect(self.flush_editor)

        # (id, label) for the rows on show, so an unchanged refresh is skipped
        # instead of rebuilding the list and dropping the reader's selection.
        self._notes: list[tuple[int, str]] = []
        self._loaded_note_id: int | None = None
        self._dirty = False

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.notes_list)
        splitter.addWidget(self.editor)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addWidget(header_row)
        layout.addWidget(splitter, 1)

    # -- interaction ---------------------------------------------------------------

    def request_new_note(self) -> None:
        """Ask the window to create a note for the active document."""
        self.note_created.emit()

    def note_clicked(self, item: QListWidgetItem) -> None:
        """Report the note the reader picked."""
        note_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(note_id, int):
            self.note_requested.emit(note_id)

    def editor_changed(self) -> None:
        """Arm the autosave debounce for a real edit."""
        if self._loaded_note_id is None:
            return
        self._dirty = True
        self.editor_timer.start()

    def flush_editor(self) -> None:
        """Save a pending edit now, before the editor changes what it holds.

        ``_dirty`` is cleared before the signal is emitted, so a call arriving
        from inside a save cannot loop back into another one.
        """
        self.editor_timer.stop()
        if not self._dirty or self._loaded_note_id is None:
            return
        self._dirty = False
        self.note_edited.emit(self._loaded_note_id, self.editor.toPlainText())

    # -- contents ------------------------------------------------------------------

    def set_notes(self, notes: Sequence[Note]) -> None:
        """Rebuild the list, unless it already shows exactly these notes."""
        rows = [(note.id, self.note_label(note)) for note in notes]
        if rows == self._notes:
            return
        self._notes = rows
        self.notes_list.blockSignals(True)
        self.notes_list.clear()
        for note_id, label in rows:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, note_id)
            item.setToolTip(label)
            self.notes_list.addItem(item)
        self.notes_list.blockSignals(False)
        self.select_note_row(self._loaded_note_id)

    def update_note(self, note: Note) -> None:
        """Refresh one row's label after its body changed the note's title."""
        label = self.note_label(note)
        for row in range(self.notes_list.count()):
            item = self.notes_list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == note.id:
                item.setText(label)
                item.setToolTip(label)
                self._notes[row] = (note.id, label)
                return

    def show_note(self, note: Note, body: str) -> None:
        """Load a note into the editor, saving whatever the editor held first."""
        self.flush_editor()
        self._loaded_note_id = note.id
        self._dirty = False
        self.editor_timer.stop()
        blocked = self.editor.blockSignals(True)
        self.editor.setPlainText(body)
        self.editor.blockSignals(blocked)
        self.editor.setReadOnly(False)
        self.select_note_row(note.id)

    def close_note(self) -> None:
        """Empty the editor, for when the document has no notes left."""
        self.flush_editor()
        self._loaded_note_id = None
        self._dirty = False
        self.editor_timer.stop()
        blocked = self.editor.blockSignals(True)
        self.editor.clear()
        self.editor.blockSignals(blocked)
        self.editor.setReadOnly(True)

    def clear(self) -> None:
        """Empty the list and the editor, for when no document is open."""
        self.notes_list.clear()
        self._notes = []
        self.close_note()

    def current_note_id(self) -> int | None:
        """Return the note the editor currently holds, if any."""
        return self._loaded_note_id

    def select_note_row(self, note_id: int | None) -> None:
        """Highlight a note's row without reporting it as a fresh selection."""
        if note_id is None:
            self.notes_list.clearSelection()
            return
        for row in range(self.notes_list.count()):
            item = self.notes_list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == note_id:
                self.notes_list.setCurrentRow(row)
                return
        self.notes_list.clearSelection()

    @staticmethod
    def note_label(note: Note) -> str:
        """Describe a note the way the list shows it."""
        if note.title:
            return note.title
        if note.page is not None:
            return f"Page {note.page + 1}"
        return "Untitled note"

    def focus_default_view(self) -> None:
        """Give the keyboard to the editor, or to the list when nothing is open."""
        if self._loaded_note_id is None:
            self.notes_list.setFocus()
        else:
            self.editor.setFocus()
