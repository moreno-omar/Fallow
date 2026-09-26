"""Menu bar, keyboard shortcuts, and the command palette.

Every shortcut is registered as a menu ``QAction`` rather than a bare
``QShortcut``: an action already carries a label, one or more key sequences, and
a ``trigger()`` slot, which is exactly what a command palette row needs. So the
menu bar is not only the user's entry point, it is also the shortcut registry
that :meth:`CommandsMixin.collect_commands` reads back.

The one exception, ``Esc``, lives in :mod:`app.ui.main_window.find` because it
belongs to the find bar rather than to a menu.
"""

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog

from app.ui.command_palette import Command, CommandPalette
from app.ui.main_window.documents import DocumentsMixin


class CommandsMixin(DocumentsMixin):
    """Build the menus and expose every shortcut to the command palette.

    Layer 7 of the window mixin chain (after ``DocumentsMixin``), so it may wire
    menu entries to every feature below it.
    """

    TAB_SEARCH_SHORTCUT = "Ctrl+Shift+A"
    DARK_MODE_SHORTCUTS = ("Ctrl+Shift+D", "Alt+D", "Ctrl+D")
    # "Ctrl++" needs Shift on many layouts, so the plain '=' binding is listed
    # too. Every entry must be unique: Qt drops shortcuts that are registered
    # twice for one action as an ambiguous overload.
    ZOOM_IN_SHORTCUTS = ("Ctrl++", "Ctrl+=")
    ZOOM_OUT_SHORTCUTS = ("Ctrl+-",)

    def create_action(self, title: str, shortcut: str, handler) -> QAction:
        """Create a window action with an optional single shortcut."""
        action = QAction(title, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(handler)
        return action

    def create_menu_bar(self) -> None:
        """Create the application menus and connect every shortcut action."""
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.create_open_action())
        file_menu.addAction(self.create_action("Close Tab", "Ctrl+W", self.close_current_tab))
        file_menu.addSeparator()
        file_menu.addAction(self.create_action("Quit", "Ctrl+Q", self.quit_application))

        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction(self.create_action("Find", "Ctrl+F", self.show_find_bar))
        edit_menu.addAction(self.create_action("Go to Page", "Ctrl+G", self.focus_page_input))
        edit_menu.addAction(self.create_action("Bookmark Page", "Ctrl+B", self.toggle_bookmark))

        view_menu = self.menuBar().addMenu("View")
        self.palette_action = self.create_action("Command Palette", "Ctrl+P", self.show_command_palette)
        view_menu.addAction(self.palette_action)
        view_menu.addAction(self.create_action("Tab Search", self.TAB_SEARCH_SHORTCUT, self.show_tab_search))
        view_menu.addSeparator()
        self.dark_mode_action = QAction("Dark Mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setShortcuts([QKeySequence(key) for key in self.DARK_MODE_SHORTCUTS])
        self.dark_mode_action.toggled.connect(self.set_dark_mode)
        view_menu.addAction(self.dark_mode_action)
        view_menu.addSeparator()
        view_menu.addAction(self.create_zoom_in_action())
        view_menu.addAction(self.create_zoom_out_action())
        view_menu.addAction(self.create_action("Reset Zoom", "Ctrl+0", self.reset_zoom))
        self.menuBar().addMenu("Help")

    def create_zoom_in_action(self) -> QAction:
        """Create the magnification action with its shortcut variants."""
        zoom_in_action = self.create_action("Zoom In", "", self.zoom_in)
        zoom_in_action.setShortcuts([QKeySequence(key) for key in self.ZOOM_IN_SHORTCUTS])
        return zoom_in_action

    def create_zoom_out_action(self) -> QAction:
        """Create the shrink action with its shortcut."""
        zoom_out_action = self.create_action("Zoom Out", "", self.zoom_out)
        zoom_out_action.setShortcuts([QKeySequence(key) for key in self.ZOOM_OUT_SHORTCUTS])
        return zoom_out_action

    def show_command_palette(self) -> None:
        """Open the searchable command palette and run the command it returns.

        The command runs only after ``exec()`` returns, so a handler that opens
        its own dialog (for example ``Open``) is never nested inside the
        palette's modal event loop.
        """
        palette = CommandPalette(self.collect_commands(), self.dark_mode, self)
        if palette.exec() == QDialog.DialogCode.Accepted and palette.selected_command is not None:
            palette.selected_command.handler()

    def collect_commands(self) -> list[Command]:
        """Build every palette entry from menu actions and viewer-level keys."""
        commands = [self.action_command(action) for action in self.menu_actions()]
        commands.extend(self.viewer_commands())
        return commands

    def menu_actions(self) -> list[QAction]:
        """Return the actionable menu entries, excluding the palette itself."""
        actions: list[QAction] = []
        for menu_action in self.menuBar().actions():
            menu = menu_action.menu()
            if menu is None:
                continue
            for action in menu.actions():
                if action.isSeparator() or action is self.palette_action:
                    continue
                actions.append(action)
        return actions

    @staticmethod
    def action_command(action: QAction) -> Command:
        """Convert a shortcut action into a palette command."""
        labels = [sequence.toString(QKeySequence.SequenceFormat.NativeText) for sequence in action.shortcuts()]
        shortcut = ", ".join(label for label in labels if label)
        return Command(action.text().replace("&", ""), shortcut, action.trigger)

    def viewer_commands(self) -> list[Command]:
        """Return commands for the keys the active viewer handles itself.

        Page turning lives in ``PDFViewerWidget`` as per-widget ``QShortcut``s,
        so these entries are not visible in the menu bar and must be added here
        for the palette to advertise them.
        """
        return [
            Command("Next Page", "Right / Down / Page Down", self.next_page),
            Command("Previous Page", "Left / Up / Page Up", self.previous_page),
        ]
