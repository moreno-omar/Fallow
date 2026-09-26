"""Dark-mode theming for the window chrome and the rendered pages.

The stylesheet colours only the Qt widgets; the PDF canvas is inverted by
``RenderEngine`` when the viewer re-renders, which is why the theme toggle has to
walk the open tabs here.
"""

from app.ui.main_window.base import WindowBase
from app.ui.viewer_tab import PDFViewerWidget


class ThemeMixin(WindowBase):
    """Switch the UI stylesheet and every open viewer between the two themes.

    Layer 2 of the window mixin chain (after ``WindowBase``).
    """

    def set_dark_mode(self, enabled: bool) -> None:
        """Apply the selected UI and PDF canvas theme."""
        self.dark_mode = enabled
        self.apply_theme()
        for index in range(self.tabs.count()):
            viewer = self.tabs.widget(index)
            if isinstance(viewer, PDFViewerWidget):
                viewer.set_dark_mode(enabled)
        self.save_session()

    def apply_theme(self) -> None:
        """Apply neutral dark or default widget styling."""
        if self.dark_mode:
            self.setStyleSheet(
                "QMainWindow, QTabWidget, QTabBar, QToolBar { background: #2E3440; color: #ECEFF4; }"
                "QScrollArea, QScrollArea > QWidget > QWidget { background: #2E3440; }"
                "QLabel, QLineEdit, QMenuBar, QMenu, QStatusBar { color: #ECEFF4; }"
                "QMenuBar::item:selected, QMenu::item:selected { background: #4C566A; }"
                "QLineEdit { background: #3B4252; border: 1px solid #81A1C1; }"
                # The notes splitter and its two panes need explicit colours for
                # the same reason as the menus: styled text on a light default
                # background is unreadable.
                "QSplitter { background: #2E3440; }"
                "QSplitter::handle { background: #4C566A; }"
                "QWidget#notesPanel { background: #292E39; border-right: 1px solid #4C566A; }"
                "QLabel#notesHeader { color: #ECEFF4; font-weight: bold; }"
                "QLabel#notesPlaceholder { color: #81A1C1; }"
                # Menus and the tab overflow button need explicit backgrounds,
                # otherwise the styled text colour lands on a light default.
                "QMenu { background: #3B4252; border: 1px solid #4C566A; }"
                "QMenu::item { padding: 4px 20px 4px 8px; }"
                "QToolButton { background: #3B4252; color: #ECEFF4; border: 1px solid #4C566A; }"
                "QToolButton:hover { background: #4C566A; }"
                "QToolButton::menu-indicator { image: none; }"
            )
        else:
            self.setStyleSheet("")
