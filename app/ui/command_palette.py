"""Searchable command palette dialog.

The palette is deliberately dumb: it does not know what a shortcut means or how a
command is implemented. ``MainWindow`` hands it a list of :class:`Command`
records, the dialog only filters, highlights, and returns the chosen one. That
keeps every action reachable in one place and lets the window stay the single
owner of behaviour.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class Command:
    """One action the palette can run.

    ``title`` and ``shortcut`` are display/search text only; ``handler`` is the
    callable the window will run after the palette closes.
    """

    title: str
    shortcut: str
    handler: Callable[[], None]


def fuzzy_score(query: str, text: str) -> int:
    """Score how well ``query`` matches ``text`` as an ordered subsequence.

    Returns ``-1`` when the query characters do not all occur in order, so
    callers can treat any negative value as "no match". Higher scores mean an
    earlier, more contiguous match that starts on a word boundary, which is what
    makes typing ``dm`` prefer "Dark Mode" over a longer late title match.

    Args:
        query: The user's typed query, compared case-insensitively.
        text: The candidate command title or shortcut label.

    Returns:
        A non-negative relevance score, or ``-1`` when nothing matched.
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return 0
    text_lower = text.lower()

    score = 0
    first_index = -1
    previous_index = -1
    for character in query_lower:
        position = text_lower.find(character, previous_index + 1)
        if position == -1:
            return -1
        if first_index == -1:
            first_index = position
        if previous_index != -1:
            # Reward adjacent characters, decay with the size of the gap.
            gap = position - previous_index - 1
            score += 4 if gap == 0 else max(0, 3 - gap)
        if position == 0 or text_lower[position - 1] in " -_/":
            score += 6
        previous_index = position

    if text_lower.startswith(query_lower):
        score += 25
    elif query_lower in text_lower:
        score += 10
    # Prefer early matches and shorter titles so the tightest match wins.
    return max(score - first_index - (len(text_lower) // 10), 0)


class CommandPalette(QDialog):
    """Modal list of commands that can be filtered by title or shortcut."""

    MAX_RESULTS = 8
    MIN_WIDTH = 460

    def __init__(self, commands: Sequence[Command], dark_mode: bool = False, parent: QWidget | None = None) -> None:
        """Build the palette for ``commands``, theming it for the current mode."""
        super().__init__(parent)
        self._commands = list(commands)
        self.selected_command: Command | None = None

        self.setWindowTitle("Command Palette")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(self.MIN_WIDTH)
        self.setStyleSheet(self._stylesheet(dark_mode))

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Type a command or shortcut")
        self.query_input.setClearButtonEnabled(True)
        self.query_input.textChanged.connect(self.refresh_results)
        # Arrow keys and Enter belong to the result list, but the text field
        # keeps focus so the user can keep typing at all times.
        self.query_input.installEventFilter(self)

        self.result_list = QListWidget()
        self.result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.result_list.setUniformItemSizes(True)
        self.result_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.result_list.itemClicked.connect(self.run_item)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.query_input)
        layout.addWidget(self.result_list)
        self.refresh_results("")

    # -- filtering -----------------------------------------------------------------

    def refresh_results(self, text: str) -> None:
        """Rebuild the result rows for ``text`` and highlight the best match."""
        matches = self.matching_commands(text)
        self.result_list.clear()
        for command in matches:
            self._add_result(command)
        self.result_list.setCurrentRow(0 if matches else -1)
        self._fit_list_height()

    def matching_commands(self, query: str) -> list[Command]:
        """Return the commands matching ``query``, best match first.

        An empty query keeps the original order, which is the order the actions
        appear in the menu bar.
        """
        if not query.strip():
            return self._commands[: self.MAX_RESULTS]

        scored: list[tuple[int, int, Command]] = []
        for index, command in enumerate(self._commands):
            score = self.score_command(query, command)
            if score is not None:
                scored.append((score, index, command))
        # Ties fall back to menu order so the list never shuffles needlessly.
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        return [command for _, _, command in scored[: self.MAX_RESULTS]]

    @staticmethod
    def score_command(query: str, command: Command) -> int | None:
        """Score one command by title, then by shortcut, or ``None`` if unmatched."""
        title_score = fuzzy_score(query, command.title)
        # Normalising away '+' lets the user type "ctrlp" or "ctrl+p".
        shortcut_text = command.shortcut.replace("+", "")
        shortcut_score = fuzzy_score(query.replace("+", ""), shortcut_text)
        scores = [title_score]
        if shortcut_score >= 0:
            # A shortcut hit is a weaker signal than a title hit.
            scores.append(max(shortcut_score - 6, 0))
        best = max(scores)
        return best if best >= 0 and (title_score >= 0 or shortcut_score >= 0) else None

    def _add_result(self, command: Command) -> None:
        """Add one row showing the command title and its shortcut."""
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, command)

        row = QWidget()
        # Clicks must reach the list view, not the labels inside the row.
        row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_label = QLabel(command.title)
        shortcut_label = QLabel(command.shortcut)
        shortcut_label.setObjectName("paletteShortcut")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 6, 8, 6)
        row_layout.setSpacing(12)
        row_layout.addWidget(title_label)
        row_layout.addStretch(1)
        row_layout.addWidget(shortcut_label)

        item.setSizeHint(row.sizeHint())
        self.result_list.addItem(item)
        self.result_list.setItemWidget(item, row)

    def _fit_list_height(self) -> None:
        """Size the list so every visible result fits without a scroll bar."""
        rows = self.result_list.count()
        if rows == 0:
            self.result_list.setVisible(False)
            self.result_list.setFixedHeight(0)
            return
        self.result_list.setVisible(True)
        row_height = self.result_list.sizeHintForRow(0)
        frame = 2 * self.result_list.frameWidth()
        self.result_list.setFixedHeight(rows * row_height + frame)

    # -- selection -----------------------------------------------------------------

    def run_item(self, item: QListWidgetItem) -> None:
        """Close the palette and remember ``item``'s command for the caller."""
        command = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(command, Command):
            self.selected_command = command
            self.accept()

    def run_current(self) -> None:
        """Accept the highlighted command (the best match by default)."""
        item = self.result_list.currentItem()
        if item is not None:
            self.run_item(item)

    def move_selection(self, step: int) -> None:
        """Move the highlight by ``step`` rows, clamped to the result list."""
        count = self.result_list.count()
        if count == 0:
            return
        current = self.result_list.currentRow()
        self.result_list.setCurrentRow(min(max(current + step, 0), count - 1))

    # -- events --------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Route Up/Down/Page keys and Enter from the query field to the list."""
        if watched is self.query_input and isinstance(event, QKeyEvent) and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_PageDown):
                self.move_selection(1)
                return True
            if key in (Qt.Key.Key_Up, Qt.Key.Key_PageUp):
                self.move_selection(-1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.run_current()
                return True
        # Escape is left to QDialog, whose default key handling rejects (closes).
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.center_on_parent()
        self.raise_()
        self.activateWindow()
        self.query_input.setFocus()

    def center_on_parent(self) -> None:
        """Position the palette in the upper third of the parent window."""
        parent = self.parentWidget()
        if parent is None:
            return
        anchor = parent.window().frameGeometry()
        self.adjustSize()
        x = anchor.x() + max((anchor.width() - self.width()) // 2, 0)
        y = anchor.y() + max((anchor.height() - self.height()) // 3, 0)
        self.move(x, y)

    @staticmethod
    def _stylesheet(dark_mode: bool) -> str:
        """Return the palette styling for the active application theme."""
        if dark_mode:
            background, surface, border, text = "#2E3440", "#3B4252", "#4C566A", "#ECEFF4"
            accent, accent_text, hint = "#5E81AC", "#ECEFF4", "#81A1C1"
        else:
            background, surface, border, text = "#F7F7F9", "#FFFFFF", "#C9CDD4", "#1F2430"
            accent, accent_text, hint = "#3B6FD4", "#FFFFFF", "#6B7280"
        return (
            f"QDialog {{ background: {background}; border: 1px solid {border}; }}"
            f"QLineEdit {{ background: {surface}; border: 1px solid {border}; color: {text}; padding: 6px 8px; }}"
            f"QListWidget {{ background: {surface}; border: 1px solid {border}; color: {text}; outline: none; }}"
            f"QListWidget::item:selected {{ background: {accent}; color: {accent_text}; }}"
            f"QLabel {{ color: {text}; }}"
            f"QLabel#paletteShortcut {{ color: {hint}; }}"
        )
